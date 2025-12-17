import secrets
import uuid
import json
from typing import Optional
from pathlib import Path
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import httpx

from config import settings as app_settings, logger
from database import get_db, Settings, InfluencerImage, Generation, PromoCode, Preset
from services.social import fetch_profile_image
from services.codes import validate_and_consume_code
from services.comfyui import generate_selfie, get_generation_status, get_queue_status
from services.payments import create_stripe_payment, create_lightning_invoice, check_payment_status

router = APIRouter(tags=["public"])
templates = Jinja2Templates(directory="templates")

# Supported image extensions
IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp")

# Temporary storage for pending Stripe payments (image + prompt before redirect)
# In production, consider using Redis or database for persistence
pending_stripe_sessions: dict[str, dict] = {}


async def create_failsafe_code(db: AsyncSession) -> Optional[str]:
    """Create a single-use promo code for failed generation retry."""
    code = f"RETRY-{secrets.token_urlsafe(6).upper()}"
    promo = PromoCode(
        code=code,
        uses_remaining=1,
        max_uses=1,
        is_active=True
    )
    db.add(promo)
    await db.commit()
    logger.info(f"Created failsafe promo code: {code}")
    return code


def sanitize_folder_name(name: str) -> str:
    """Sanitize a preset name for use as a folder name."""
    safe = "".join(c if c.isalnum() or c in "._- " else "" for c in name)
    safe = safe.replace(" ", "_").strip("._- ")
    return safe or "default"


def get_example_images_from_disk(preset_name: Optional[str] = None) -> list[dict]:
    """Get example images directly from the generated directory.
    If preset_name is provided, try static/uploads/generated/<preset_name>/ first,
    otherwise fall back to static/uploads/generated/ root.
    """
    generated_dir = app_settings.upload_dir / "generated"
    # If preset-specific folder exists, prefer it
    if preset_name is not None:
        preset_dir = generated_dir / sanitize_folder_name(preset_name)
        if preset_dir.exists():
            generated_dir = preset_dir
    examples = []
    
    if generated_dir.exists():
        for img_path in sorted([p for p in generated_dir.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS], key=lambda p: p.stat().st_mtime, reverse=True):
            # Build URL reflecting preset subfolder if present
            rel_path = img_path.relative_to(app_settings.upload_dir)
            examples.append({
                "url": f"/uploads/{rel_path.as_posix()}",
                "name": img_path.stem
            })
    
    return examples


@router.get("/", response_class=HTMLResponse)
async def home(request: Request, db: AsyncSession = Depends(get_db)):
    """Main fan-facing page."""
    # Get settings
    settings = await db.get(Settings, 1)
    
    # Get active presets
    result = await db.execute(
        select(Preset)
        .where(Preset.is_active == True)
        .order_by(Preset.sort_order, Preset.created_at)
    )
    presets = result.scalars().all()
    
    # Get example images from disk (initially for first active preset if available)
    first_preset_name = presets[0].name if presets else None
    examples = get_example_images_from_disk(first_preset_name)
    
    return templates.TemplateResponse("index.html", {
        "request": request,
        "settings": settings,
        "examples": examples,
        "presets": presets,
    })


@router.get("/api/examples")
async def api_examples(preset_id: Optional[int] = None, db: AsyncSession = Depends(get_db)):
    """Return example images for an optional preset_id."""
    preset_name = None
    if preset_id is not None:
        try:
            preset = await db.get(Preset, int(preset_id))
            if preset:
                preset_name = preset.name
        except (TypeError, ValueError):
            pass
    examples = get_example_images_from_disk(preset_name)
    return JSONResponse({"examples": examples})


@router.get("/api/server-status")
async def server_status():
    """Check ComfyUI server status and queue size."""
    import httpx
    
    comfyui_url = app_settings.comfyui_url
    logger.info(f"Checking ComfyUI status at: {comfyui_url}")
    
    # Directly check if ComfyUI is reachable
    error_msg = None
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{comfyui_url}/queue")
            logger.info(f"ComfyUI response status: {response.status_code}")
            if response.status_code == 200:
                queue = response.json()
                pending = len(queue.get("queue_pending", []))
                running = len(queue.get("queue_running", []))
                
                return JSONResponse({
                    "online": True,
                    "queue_pending": pending,
                    "queue_running": running,
                    "queue_total": pending + running,
                    "url": comfyui_url
                })
            else:
                error_msg = f"HTTP {response.status_code}"
    except httpx.ConnectError as e:
        error_msg = f"Connection error: {e}"
        logger.warning(f"ComfyUI connect error: {e}")
    except httpx.TimeoutException as e:
        error_msg = f"Timeout: {e}"
        logger.warning(f"ComfyUI timeout: {e}")
    except Exception as e:
        error_msg = str(e)
        logger.warning(f"ComfyUI check failed: {e}")
    
    return JSONResponse({
        "online": False,
        "queue_pending": 0,
        "queue_running": 0,
        "queue_total": 0,
        "url": comfyui_url,
        "error": error_msg
    })


@router.post("/api/validate-code")
async def validate_code(
    code: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    """Validate a promo code without consuming it."""
    result = await db.execute(
        select(PromoCode)
        .where(PromoCode.code == code.upper().strip())
        .where(PromoCode.is_active == True)
    )
    promo = result.scalar_one_or_none()
    
    if not promo:
        return JSONResponse({"valid": False, "error": "Invalid code"})
    
    # Check uses remaining
    if promo.uses_remaining is not None and promo.uses_remaining <= 0:
        return JSONResponse({"valid": False, "error": "Code has been fully used"})
    
    # Check expiry
    from datetime import datetime
    if promo.expires_at and promo.expires_at < datetime.utcnow():
        return JSONResponse({"valid": False, "error": "Code has expired"})
    
    return JSONResponse({"valid": True})


@router.post("/api/fetch-profile")
async def fetch_profile(
    platform: str = Form(...),
    handle: str = Form(...)
):
    """Fetch profile image from social media platform."""
    try:
        image_url = await fetch_profile_image(platform, handle)
        if image_url:
            return JSONResponse({"success": True, "image_url": image_url})
        return JSONResponse({"success": False, "error": "Could not fetch profile image"})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)})


@router.post("/api/create-payment")
async def create_payment(
    request: Request,
    payment_type: str = Form(...),  # stripe or lightning
    preset_id: Optional[int] = Form(None),
    platform: Optional[str] = Form(None),
    handle: Optional[str] = Form(None),
    custom_prompt: Optional[str] = Form(None),
    uploaded_image: Optional[UploadFile] = File(None),
    existing_image_url: Optional[str] = Form(None),  # For social media fetched images
    db: AsyncSession = Depends(get_db)
):
    """Create a payment intent or lightning invoice.
    
    For Stripe payments, also stores the uploaded image and prompt so they
    persist across the redirect to Stripe and back.
    """
    settings = await db.get(Settings, 1)
    
    # Get price from preset
    if not preset_id:
        raise HTTPException(status_code=400, detail="Preset ID required")
    
    preset = await db.get(Preset, preset_id)
    if not preset or not preset.is_active:
        raise HTTPException(status_code=400, detail="Invalid or inactive preset")
    
    price_cents = preset.price_cents
    
    if payment_type == "stripe":
        if not settings.stripe_enabled:
            raise HTTPException(status_code=400, detail="Stripe payments not enabled")
        
        # Generate a pending session ID to track the image/prompt
        pending_id = uuid.uuid4().hex
        
        # Store uploaded image if provided, or use existing image URL
        stored_image_path = None
        if uploaded_image and uploaded_image.filename:
            ext = uploaded_image.filename.split(".")[-1]
            filename = f"pending_{pending_id}.{ext}"
            filepath = app_settings.upload_dir / filename
            content = await uploaded_image.read()
            with open(filepath, "wb") as f:
                f.write(content)
            stored_image_path = str(filepath)
        elif existing_image_url:
            # Image was fetched from social media - extract filename from URL
            # URL format: /uploads/filename.ext
            if existing_image_url.startswith("/uploads/"):
                filename = existing_image_url.replace("/uploads/", "")
                filepath = app_settings.upload_dir / filename
                if filepath.exists():
                    stored_image_path = str(filepath)
        
        # Store pending session data
        pending_stripe_sessions[pending_id] = {
            "image_path": stored_image_path,
            "platform": platform,
            "handle": handle,
            "custom_prompt": custom_prompt,
            "preset_id": preset_id,
        }
        
        # Use PUBLIC_URL env var if set (for RunPod/proxy setups), otherwise use request base URL
        if app_settings.public_url:
            base_url = app_settings.public_url.rstrip("/")
        else:
            base_url = str(request.base_url).rstrip("/")
        
        success_url = f"{base_url}/?payment=success&session_id={{CHECKOUT_SESSION_ID}}&preset_id={preset_id}&pending_id={pending_id}"
        cancel_url = f"{base_url}/?payment=cancelled&pending_id={pending_id}"
        
        result = await create_stripe_payment(price_cents, settings.currency, success_url, cancel_url)
        return JSONResponse(result)
    
    elif payment_type == "lightning":
        if not settings.lightning_enabled:
            raise HTTPException(status_code=400, detail="Lightning payments not enabled")
        result = await create_lightning_invoice(price_cents, settings.currency)
        return JSONResponse(result)
    
    raise HTTPException(status_code=400, detail="Invalid payment type")


@router.get("/api/payment-status/{payment_id}")
async def payment_status(payment_id: str, payment_type: str):
    """Check payment status."""
    result = await check_payment_status(payment_type, payment_id)
    return JSONResponse(result)


@router.get("/api/pending-session/{pending_id}")
async def get_pending_session(pending_id: str):
    """Retrieve pending session data after Stripe redirect.
    
    Returns the stored image path and custom prompt so the frontend
    can restore state after returning from Stripe checkout.
    """
    session_data = pending_stripe_sessions.get(pending_id)
    if not session_data:
        return JSONResponse({"found": False})
    
    # Build response with image URL if we have a stored image
    response = {
        "found": True,
        "platform": session_data.get("platform"),
        "handle": session_data.get("handle"),
        "custom_prompt": session_data.get("custom_prompt"),
        "preset_id": session_data.get("preset_id"),
        "image_url": None
    }
    
    if session_data.get("image_path"):
        # Convert filesystem path to URL
        image_path = Path(session_data["image_path"])
        if image_path.exists():
            response["image_url"] = f"/uploads/{image_path.name}"
    
    return JSONResponse(response)


@router.post("/api/generate")
async def generate(
    request: Request,
    payment_method: str = Form(...),  # code, stripe, lightning
    payment_id: Optional[str] = Form(None),
    promo_code: Optional[str] = Form(None),
    platform: Optional[str] = Form(None),
    handle: Optional[str] = Form(None),
    preset_id: Optional[int] = Form(None),
    custom_prompt: Optional[str] = Form(None),
    pending_id: Optional[str] = Form(None),  # For Stripe: retrieve stored image/prompt
    uploaded_image: Optional[UploadFile] = File(None),
    db: AsyncSession = Depends(get_db)
):
    """Generate a selfie after payment verification."""
    settings = await db.get(Settings, 1)
    
    # For Stripe payments, retrieve stored session data if pending_id provided
    pending_session = None
    if pending_id and pending_id in pending_stripe_sessions:
        pending_session = pending_stripe_sessions.pop(pending_id)  # Remove after use
        # Use stored values if not provided in request
        if not custom_prompt and pending_session.get("custom_prompt"):
            custom_prompt = pending_session["custom_prompt"]
        if not preset_id and pending_session.get("preset_id"):
            preset_id = pending_session["preset_id"]
        if not platform and pending_session.get("platform"):
            platform = pending_session["platform"]
        if not handle and pending_session.get("handle"):
            handle = pending_session["handle"]
    
    # Get preset if specified
    preset = None
    if preset_id:
        preset = await db.get(Preset, preset_id)
        if not preset or not preset.is_active:
            raise HTTPException(status_code=400, detail="Invalid or inactive preset")
    
    # Verify payment
    if payment_method == "code":
        if not settings.codes_enabled:
            raise HTTPException(status_code=400, detail="Promo codes not enabled")
        if not promo_code:
            raise HTTPException(status_code=400, detail="Promo code required")
        
        success, error = await validate_and_consume_code(db, promo_code)
        if not success:
            raise HTTPException(status_code=400, detail=error)
    
    elif payment_method == "stripe":
        if not payment_id:
            raise HTTPException(status_code=400, detail="Payment ID required")
        status = await check_payment_status("stripe", payment_id)
        if not status.get("paid"):
            raise HTTPException(status_code=400, detail="Payment not completed")
    
    elif payment_method == "lightning":
        if not payment_id:
            raise HTTPException(status_code=400, detail="Payment ID required")
        status = await check_payment_status("lightning", payment_id)
        if not status.get("paid"):
            raise HTTPException(status_code=400, detail="Payment not completed")
    
    else:
        raise HTTPException(status_code=400, detail="Invalid payment method")
    
    # Get fan image
    fan_image_url = None
    fan_image_path = None  # Filesystem path for ComfyUI
    
    # First check if we have a stored image from pending Stripe session
    if pending_session and pending_session.get("image_path"):
        stored_path = Path(pending_session["image_path"])
        if stored_path.exists():
            fan_image_url = f"/uploads/{stored_path.name}"
            fan_image_path = str(stored_path)
            platform = "upload"
            handle = None
    elif uploaded_image and uploaded_image.filename:
        # Save uploaded image temporarily
        ext = uploaded_image.filename.split(".")[-1]
        filename = f"fan_{uuid.uuid4().hex}.{ext}"
        filepath = app_settings.upload_dir / filename
        content = await uploaded_image.read()
        with open(filepath, "wb") as f:
            f.write(content)
        fan_image_url = f"/uploads/{filename}"
        fan_image_path = str(filepath)
        # Override platform/handle for uploaded images
        platform = "upload"
        handle = None
    elif platform and handle:
        fan_image_url = await fetch_profile_image(platform, handle)
        fan_image_path = fan_image_url  # URL for social media images
    
    if not fan_image_url:
        raise HTTPException(status_code=400, detail="No fan image provided")
    
    # Get influencer image(s) - use preset's image if specified, otherwise use all
    if preset:
        # Use the specific influencer image from the preset
        influencer_image = await db.get(InfluencerImage, preset.influencer_image_id)
        if not influencer_image:
            raise HTTPException(status_code=400, detail="Preset's influencer image not found")
        influencer_images = [influencer_image]
    else:
        # Fall back to all influencer images
        result = await db.execute(select(InfluencerImage))
        influencer_images = result.scalars().all()
    
    if not influencer_images:
        raise HTTPException(status_code=400, detail="No influencer images configured")
    
    # Create generation record
    generation = Generation(
        fan_image_url=fan_image_url,
        fan_platform=platform,
        fan_handle=handle,
        payment_method=payment_method,
        promo_code_used=promo_code,
        payment_id=payment_id,
        status="pending"
    )
    db.add(generation)
    await db.commit()
    await db.refresh(generation)
    
    # Determine which prompt to use
    # Use custom_prompt only if preset allows prompt editing
    final_prompt = None
    if preset:
        if preset.allow_prompt_edit and custom_prompt:
            final_prompt = custom_prompt
        else:
            final_prompt = preset.prompt
    
    # Start generation with preset settings if available
    try:
        prompt_id = await generate_selfie(
            fan_image_url=fan_image_path,
            influencer_images=[img.filename for img in influencer_images],
            width=preset.width if preset else None,
            height=preset.height if preset else None,
            prompt=final_prompt
        )
        generation.prompt_id = prompt_id
        generation.status = "processing"
        await db.commit()
        
        return JSONResponse({
            "success": True,
            "generation_id": generation.id,
            "prompt_id": prompt_id
        })
    except Exception as e:
        generation.status = "failed"
        await db.commit()
        raise HTTPException(status_code=500, detail=str(e))


async def download_and_save_result(generation_id: int, comfyui_url: str) -> str:
    """Download image from ComfyUI and save locally. Returns local URL."""
    results_dir = app_settings.upload_dir / "results"
    results_dir.mkdir(exist_ok=True, parents=True)
    
    filename = f"selfie_{generation_id}.png"
    save_path = results_dir / filename
    
    async with httpx.AsyncClient() as client:
        response = await client.get(comfyui_url)
        response.raise_for_status()
        
        with open(save_path, "wb") as f:
            f.write(response.content)
    
    return f"/uploads/results/{filename}"


@router.get("/api/generation-status/{generation_id}")
async def generation_status(generation_id: int, db: AsyncSession = Depends(get_db)):
    """Check generation status and get result."""
    generation = await db.get(Generation, generation_id)
    if not generation:
        raise HTTPException(status_code=404, detail="Generation not found")
    
    if generation.status == "completed":
        return JSONResponse({
            "status": "completed",
            "result_url": generation.result_image_url
        })
    
    if generation.status == "failed":
        # Check if there's already a retry code for this generation
        retry_code = generation.retry_code if hasattr(generation, 'retry_code') else None
        return JSONResponse({"status": "failed", "retry_code": retry_code})
    
    if generation.prompt_id:
        # Check ComfyUI status
        result = await get_generation_status(generation.prompt_id)
        if result.get("completed"):
            comfyui_url = result.get("image_url")
            # Download and save locally
            try:
                local_url = await download_and_save_result(generation_id, comfyui_url)
                generation.status = "completed"
                generation.result_image_url = local_url
                from datetime import datetime
                generation.completed_at = datetime.utcnow()
                await db.commit()
                return JSONResponse({
                    "status": "completed",
                    "result_url": local_url
                })
            except Exception as e:
                generation.status = "failed"
                
                # Create failsafe retry code if enabled
                retry_code = None
                settings = await db.get(Settings, 1)
                if settings and settings.failsafe_enabled and not generation.retry_code:
                    retry_code = await create_failsafe_code(db)
                    generation.retry_code = retry_code
                
                await db.commit()
                return JSONResponse({"status": "failed", "error": str(e), "retry_code": retry_code})
    
    return JSONResponse({"status": generation.status})
