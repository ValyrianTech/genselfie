import secrets
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings as app_settings
from database import get_db, Settings, InfluencerImage, PromoCode, Generation, Preset

router = APIRouter(tags=["admin"])
templates = Jinja2Templates(directory="templates")

# Supported image extensions
IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp")

# Simple session storage (in production, use proper session management)
admin_sessions: set[str] = set()


def get_example_inputs_from_disk() -> list[dict]:
    """Get example input images from the examples directory."""
    examples_dir = app_settings.upload_dir / "examples"
    inputs = []
    
    if examples_dir.exists():
        for img_path in sorted([p for p in examples_dir.iterdir() if p.suffix.lower() in IMAGE_EXTENSIONS], key=lambda p: p.name):
            inputs.append({
                "filename": img_path.name,
                "name": img_path.stem,
                "url": f"/uploads/examples/{img_path.name}"
            })
    
    return inputs


def sanitize_folder_name(name: str) -> str:
    """Sanitize a preset name for use as a folder name."""
    # Replace spaces with underscores, keep only alphanumeric and basic chars
    safe = "".join(c if c.isalnum() or c in "._- " else "" for c in name)
    safe = safe.replace(" ", "_").strip("._- ")
    return safe or "default"


def get_generated_examples_from_disk(preset_name: Optional[str] = None) -> list[dict]:
    """Get generated example images.
    If preset_name is provided, read from generated/<preset_name>/, else include root generated/ and all preset subfolders.
    Returns entries with relpath (relative to uploads root) for deletion routing.
    """
    generated_dir = app_settings.upload_dir / "generated"
    examples: list[dict] = []
    
    if not generated_dir.exists():
        return examples
    
    def add_from_dir(dir_path: Path, folder_name: Optional[str]):
        for img_path in sorted([p for p in dir_path.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS], key=lambda p: p.stat().st_mtime, reverse=True):
            rel_from_uploads = img_path.relative_to(app_settings.upload_dir)
            examples.append({
                "relpath": rel_from_uploads.as_posix(),
                "filename": img_path.name,
                "name": img_path.stem,
                "preset_name": folder_name,
                "url": f"/uploads/{rel_from_uploads.as_posix()}"
            })
    
    if preset_name is not None:
        preset_dir = generated_dir / sanitize_folder_name(preset_name)
        if preset_dir.exists():
            add_from_dir(preset_dir, preset_name)
        else:
            # if no specific folder, fall back to root
            add_from_dir(generated_dir, None)
    else:
        # Include root images
        add_from_dir(generated_dir, None)
        # Include subfolder images by folder name
        for sub in sorted([p for p in generated_dir.iterdir() if p.is_dir()]):
            add_from_dir(sub, sub.name)
    
    return examples


def get_session_token(request: Request) -> Optional[str]:
    """Get session token from cookie."""
    return request.cookies.get("admin_session")


def verify_admin(request: Request) -> bool:
    """Verify admin is logged in."""
    token = get_session_token(request)
    return token in admin_sessions if token else False


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def admin_page(request: Request, db: AsyncSession = Depends(get_db)):
    """Admin panel main page."""
    if not verify_admin(request):
        return templates.TemplateResponse("admin_login.html", {"request": request})
    
    # Get settings
    settings = await db.get(Settings, 1)
    
    # Get influencer images
    result = await db.execute(select(InfluencerImage).order_by(InfluencerImage.created_at.desc()))
    images = result.scalars().all()
    
    # Get promo codes
    result = await db.execute(select(PromoCode).order_by(PromoCode.created_at.desc()))
    codes = result.scalars().all()
    
    # Get recent generations
    result = await db.execute(select(Generation).order_by(Generation.created_at.desc()).limit(20))
    generations = result.scalars().all()
    
    # Get example inputs from disk
    example_inputs = get_example_inputs_from_disk()
    
    # Get presets first (needed for filtering)
    result = await db.execute(select(Preset).order_by(Preset.sort_order, Preset.created_at))
    presets = result.scalars().all()
    preset_names = {p.id: p.name for p in presets}
    
    # Filter generated examples by optional preset_id query param
    selected_preset_id: Optional[int] = None
    selected_preset_name: Optional[str] = None
    q_pid = request.query_params.get("preset_id")
    if q_pid:
        try:
            selected_preset_id = int(q_pid)
            selected_preset_name = preset_names.get(selected_preset_id)
        except ValueError:
            selected_preset_id = None
    generated_examples = get_generated_examples_from_disk(selected_preset_name)
    
    # Create mapping of image IDs to names for display
    image_names = {img.id: img.original_name for img in images}
    
    return templates.TemplateResponse("admin.html", {
        "request": request,
        "settings": settings,
        "images": images,
        "image_names": image_names,
        "codes": codes,
        "generations": generations,
        "example_inputs": example_inputs,
        "generated_examples": generated_examples,
        "selected_preset_id": selected_preset_id,
        "presets": presets,
        "preset_names": preset_names,
        "comfyui_url": app_settings.comfyui_url,
        "stripe_secret_key": app_settings.stripe_secret_key,
        "stripe_publishable_key": app_settings.stripe_publishable_key,
        "lnbits_url": app_settings.lnbits_url,
        "lnbits_api_key": app_settings.lnbits_api_key,
    })


@router.post("/login")
async def admin_login(request: Request, password: str = Form(...)):
    """Admin login."""
    if password == app_settings.admin_password:
        token = secrets.token_urlsafe(32)
        admin_sessions.add(token)
        response = RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)
        response.set_cookie("admin_session", token, httponly=True, max_age=86400)
        return response
    
    return templates.TemplateResponse("admin_login.html", {
        "request": request,
        "error": "Invalid password"
    })


@router.post("/logout")
async def admin_logout(request: Request):
    """Admin logout."""
    token = get_session_token(request)
    if token:
        admin_sessions.discard(token)
    response = RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie("admin_session")
    return response


@router.post("/settings")
async def update_settings(
    request: Request,
    app_name: str = Form(...),
    tagline: str = Form(""),
    primary_color: str = Form("#6366f1"),
    secondary_color: str = Form("#8b5cf6"),
    currency: str = Form("USD"),
    stripe_enabled: bool = Form(False),
    lightning_enabled: bool = Form(False),
    codes_enabled: bool = Form(False),
    comfyui_url: str = Form(""),
    db: AsyncSession = Depends(get_db)
):
    """Update app settings."""
    if not verify_admin(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    settings = await db.get(Settings, 1)
    settings.app_name = app_name
    settings.tagline = tagline
    settings.primary_color = primary_color
    settings.secondary_color = secondary_color
    settings.currency = currency
    settings.stripe_enabled = stripe_enabled
    settings.lightning_enabled = lightning_enabled
    settings.codes_enabled = codes_enabled
    
    await db.commit()
    return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/upload-banner")
async def upload_banner(
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    """Upload banner image."""
    if not verify_admin(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    # Save file
    ext = Path(file.filename).suffix
    filename = f"banner_{uuid.uuid4().hex}{ext}"
    filepath = app_settings.upload_dir / filename
    
    content = await file.read()
    with open(filepath, "wb") as f:
        f.write(content)
    
    # Update settings
    settings = await db.get(Settings, 1)
    settings.banner_image = filename
    await db.commit()
    
    return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/upload-logo")
async def upload_logo(
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    """Upload logo image."""
    if not verify_admin(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    # Save file
    ext = Path(file.filename).suffix
    filename = f"logo_{uuid.uuid4().hex}{ext}"
    filepath = app_settings.upload_dir / filename
    
    content = await file.read()
    with open(filepath, "wb") as f:
        f.write(content)
    
    # Update settings
    settings = await db.get(Settings, 1)
    settings.logo_image = filename
    await db.commit()
    
    return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/upload-influencer-image")
async def upload_influencer_image(
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    """Upload influencer reference image."""
    if not verify_admin(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    # Save file
    ext = Path(file.filename).suffix
    filename = f"influencer_{uuid.uuid4().hex}{ext}"
    filepath = app_settings.upload_dir / filename
    
    content = await file.read()
    with open(filepath, "wb") as f:
        f.write(content)
    
    # Create record
    image = InfluencerImage(
        filename=filename,
        original_name=file.filename
    )
    db.add(image)
    await db.commit()
    
    return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/delete-influencer-image/{image_id}")
async def delete_influencer_image(
    request: Request,
    image_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Delete influencer image."""
    if not verify_admin(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    image = await db.get(InfluencerImage, image_id)
    if image:
        # Delete file
        filepath = app_settings.upload_dir / image.filename
        if filepath.exists():
            filepath.unlink()
        
        await db.delete(image)
        await db.commit()
    
    return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)


def generate_random_code(length: int = 8) -> str:
    """Generate a random promo code."""
    import string
    chars = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(chars) for _ in range(length))


@router.post("/create-code")
async def create_promo_code(
    request: Request,
    code: str = Form(""),
    max_uses: Optional[int] = Form(None),
    expires_at: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db)
):
    """Create a new promo code."""
    if not verify_admin(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    # Generate random code if empty
    code = code.strip().upper()
    if not code:
        code = generate_random_code()
    
    # Parse expiry date
    expiry = None
    if expires_at:
        try:
            expiry = datetime.fromisoformat(expires_at)
        except ValueError:
            pass
    
    promo = PromoCode(
        code=code,
        uses_remaining=max_uses,
        max_uses=max_uses,
        expires_at=expiry
    )
    db.add(promo)
    
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Code already exists")
    
    return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/delete-code/{code_id}")
async def delete_promo_code(
    request: Request,
    code_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Delete a promo code."""
    if not verify_admin(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    code = await db.get(PromoCode, code_id)
    if code:
        await db.delete(code)
        await db.commit()
    
    return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/comfyui-url")
async def update_comfyui_url(
    request: Request,
    comfyui_url: str = Form("")
):
    """Update ComfyUI server URL in .env file."""
    if not verify_admin(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    from dotenv import set_key
    from config import ENV_PATH
    
    # Clean and format the URL - trim spaces and add http:// prefix
    clean_url = comfyui_url.strip()
    if clean_url and not clean_url.startswith(("http://", "https://")):
        clean_url = f"http://{clean_url}"
    
    # Update .env file
    set_key(str(ENV_PATH), "COMFYUI_URL", clean_url)
    
    # Update runtime config
    app_settings.comfyui_url = clean_url
    
    return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/stripe-settings")
async def update_stripe_settings(
    request: Request,
    stripe_secret_key: str = Form(""),
    stripe_publishable_key: str = Form("")
):
    """Update Stripe API keys in .env file."""
    if not verify_admin(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    from dotenv import set_key
    from config import ENV_PATH
    
    # Update .env file
    set_key(str(ENV_PATH), "STRIPE_SECRET_KEY", stripe_secret_key.strip())
    set_key(str(ENV_PATH), "STRIPE_PUBLISHABLE_KEY", stripe_publishable_key.strip())
    
    # Update runtime config
    app_settings.stripe_secret_key = stripe_secret_key.strip()
    app_settings.stripe_publishable_key = stripe_publishable_key.strip()
    
    return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/lnbits-settings")
async def update_lnbits_settings(
    request: Request,
    lnbits_url: str = Form(""),
    lnbits_api_key: str = Form("")
):
    """Update LNbits settings in .env file."""
    if not verify_admin(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    from dotenv import set_key
    from config import ENV_PATH
    
    # Clean URL
    clean_url = lnbits_url.strip().rstrip("/")
    
    # Update .env file
    set_key(str(ENV_PATH), "LNBITS_URL", clean_url)
    set_key(str(ENV_PATH), "LNBITS_API_KEY", lnbits_api_key.strip())
    
    # Update runtime config
    app_settings.lnbits_url = clean_url
    app_settings.lnbits_api_key = lnbits_api_key.strip()
    
    return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/upload-example-input")
async def upload_example_input(
    request: Request,
    file: UploadFile = File(...)
):
    """Upload an example input image."""
    if not verify_admin(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    # Ensure examples directory exists
    examples_dir = app_settings.upload_dir / "examples"
    examples_dir.mkdir(exist_ok=True)
    
    # Save file with original name (sanitized)
    original_name = Path(file.filename).stem
    ext = Path(file.filename).suffix or ".png"
    # Sanitize filename
    safe_name = "".join(c for c in original_name if c.isalnum() or c in "._- ")
    filename = f"{safe_name}{ext}"
    filepath = examples_dir / filename
    
    # If file exists, add a suffix
    counter = 1
    while filepath.exists():
        filename = f"{safe_name}_{counter}{ext}"
        filepath = examples_dir / filename
        counter += 1
    
    content = await file.read()
    with open(filepath, "wb") as f:
        f.write(content)
    
    return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/delete-example-input/{filename:path}")
async def delete_example_input(
    request: Request,
    filename: str
):
    """Delete an example input image."""
    if not verify_admin(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    filepath = app_settings.upload_dir / "examples" / filename
    if filepath.exists():
        filepath.unlink()
    
    return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/generate-example/{filename:path}")
async def generate_example(
    request: Request,
    filename: str,
    preset_id: int = Form(...),
    db: AsyncSession = Depends(get_db)
):
    """Generate an example selfie from an example input for a specific preset."""
    if not verify_admin(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    from services.comfyui import generate_selfie, upload_image_to_comfyui, download_output_image, get_generation_status
    import asyncio
    
    # Verify file exists
    example_path = app_settings.upload_dir / "examples" / filename
    if not example_path.exists():
        raise HTTPException(status_code=404, detail="Example input not found")
    
    # Get preset and influencer image
    preset = await db.get(Preset, preset_id)
    if not preset or not preset.is_active:
        raise HTTPException(status_code=400, detail="Invalid or inactive preset")
    influencer = await db.get(InfluencerImage, preset.influencer_image_id)
    if not influencer:
        raise HTTPException(status_code=400, detail="Preset's influencer image not found")
    
    # Upload example input image to ComfyUI
    await upload_image_to_comfyui(example_path)
    
    # Start generation
    prompt_id = await generate_selfie(
        fan_image_url=str(example_path),
        influencer_images=[influencer.filename],
        width=preset.width,
        height=preset.height,
        prompt=preset.prompt
    )
    
    # Poll for completion and download result
    for _ in range(120):  # Wait up to 2 minutes
        await asyncio.sleep(1)
        status_result = await get_generation_status(prompt_id)
        if status_result.get("completed"):
            image_url = status_result.get("image_url")
            if image_url:
                # Download and save under preset-specific folder (using preset name)
                folder_name = sanitize_folder_name(preset.name)
                generated_dir = app_settings.upload_dir / "generated" / folder_name
                generated_dir.mkdir(exist_ok=True, parents=True)
                output_filename = f"{example_path.stem}_{uuid.uuid4().hex[:8]}.png"
                save_path = generated_dir / output_filename
                await download_output_image(image_url, save_path)
            break
    
    return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/generate-all-examples")
async def generate_all_examples(
    request: Request,
    preset_id: int = Form(...),
    db: AsyncSession = Depends(get_db)
):
    """Generate example selfies for all example inputs for a specific preset."""
    if not verify_admin(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    from services.comfyui import generate_selfie, upload_image_to_comfyui, download_output_image, get_generation_status
    import asyncio
    
    # Get all example inputs from disk
    example_inputs = get_example_inputs_from_disk()
    
    # Get preset and influencer image
    preset = await db.get(Preset, preset_id)
    if not preset or not preset.is_active:
        raise HTTPException(status_code=400, detail="Invalid or inactive preset")
    influencer = await db.get(InfluencerImage, preset.influencer_image_id)
    if not influencer:
        raise HTTPException(status_code=400, detail="Preset's influencer image not found")
    
    # Track all prompt IDs
    generations = []
    
    for example in example_inputs:
        example_path = app_settings.upload_dir / "examples" / example["filename"]
        await upload_image_to_comfyui(example_path)
        
        try:
            prompt_id = await generate_selfie(
                fan_image_url=str(example_path),
                influencer_images=[influencer.filename],
                width=preset.width,
                height=preset.height,
                prompt=preset.prompt
            )
            generations.append({"prompt_id": prompt_id, "name": example["name"]})
        except Exception as e:
            print(f"[ERROR] Failed to generate for {example['name']}: {e}")
    
    # Poll for completions and download results (using preset name for folder)
    folder_name = sanitize_folder_name(preset.name)
    generated_dir = app_settings.upload_dir / "generated" / folder_name
    generated_dir.mkdir(exist_ok=True, parents=True)
    
    for gen in generations:
        for _ in range(120):  # Wait up to 2 minutes per image
            await asyncio.sleep(1)
            status_result = await get_generation_status(gen["prompt_id"])
            if status_result.get("completed"):
                image_url = status_result.get("image_url")
                if image_url:
                    output_filename = f"{gen['name']}_{uuid.uuid4().hex[:8]}.png"
                    save_path = generated_dir / output_filename
                    await download_output_image(image_url, save_path)
                break
    
    return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/delete-generated/{filepath:path}")
async def delete_generated(
    request: Request,
    filepath: str
):
    """Delete a generated example image."""
    if not verify_admin(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    # filepath is relative to uploads dir (e.g., "generated/preset/image.png")
    full_path = app_settings.upload_dir / filepath
    if full_path.exists():
        full_path.unlink()
    
    return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)


# ============== Preset Management ==============

@router.post("/create-preset")
async def create_preset(
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    influencer_image_id: int = Form(...),
    width: int = Form(1024),
    height: int = Form(1024),
    prompt: str = Form(""),
    price_cents: int = Form(500),
    allow_prompt_edit: bool = Form(False),
    db: AsyncSession = Depends(get_db)
):
    """Create a new preset."""
    if not verify_admin(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    # Get max sort order
    result = await db.execute(select(Preset).order_by(Preset.sort_order.desc()).limit(1))
    last_preset = result.scalar_one_or_none()
    sort_order = (last_preset.sort_order + 1) if last_preset else 0
    
    preset = Preset(
        name=name,
        description=description if description else None,
        influencer_image_id=influencer_image_id,
        width=width,
        height=height,
        prompt=prompt if prompt else None,
        price_cents=price_cents,
        allow_prompt_edit=allow_prompt_edit,
        sort_order=sort_order
    )
    db.add(preset)
    await db.commit()
    
    return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/update-preset/{preset_id}")
async def update_preset(
    request: Request,
    preset_id: int,
    name: str = Form(...),
    description: str = Form(""),
    influencer_image_id: int = Form(...),
    width: int = Form(1024),
    height: int = Form(1024),
    prompt: str = Form(""),
    price_cents: int = Form(500),
    allow_prompt_edit: bool = Form(False),
    is_active: bool = Form(False),
    db: AsyncSession = Depends(get_db)
):
    """Update an existing preset."""
    if not verify_admin(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    preset = await db.get(Preset, preset_id)
    if not preset:
        raise HTTPException(status_code=404, detail="Preset not found")
    
    preset.name = name
    preset.description = description if description else None
    preset.influencer_image_id = influencer_image_id
    preset.width = width
    preset.height = height
    preset.prompt = prompt if prompt else None
    preset.price_cents = price_cents
    preset.allow_prompt_edit = allow_prompt_edit
    preset.is_active = is_active
    
    await db.commit()
    
    return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/delete-preset/{preset_id}")
async def delete_preset(
    request: Request,
    preset_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Delete a preset."""
    if not verify_admin(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    preset = await db.get(Preset, preset_id)
    if preset:
        await db.delete(preset)
        await db.commit()
    
    return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/toggle-preset/{preset_id}")
async def toggle_preset(
    request: Request,
    preset_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Toggle a preset's active status."""
    if not verify_admin(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    preset = await db.get(Preset, preset_id)
    if preset:
        preset.is_active = not preset.is_active
        await db.commit()
    
    return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)
