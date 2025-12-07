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
from database import get_db, Settings, InfluencerImage, PromoCode, Generation, ExampleImage

router = APIRouter(tags=["admin"])
templates = Jinja2Templates(directory="templates")

# Simple session storage (in production, use proper session management)
admin_sessions: set[str] = set()


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
    
    # Get example images
    result = await db.execute(select(ExampleImage).order_by(ExampleImage.created_at.desc()))
    examples = result.scalars().all()
    
    return templates.TemplateResponse("admin.html", {
        "request": request,
        "settings": settings,
        "images": images,
        "codes": codes,
        "generations": generations,
        "examples": examples,
        "comfyui_url": app_settings.comfyui_url,
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
    price_cents: int = Form(500),
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
    settings.price_cents = price_cents
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
    is_primary: bool = Form(False),
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
    
    # If this is primary, unset other primaries
    if is_primary:
        result = await db.execute(select(InfluencerImage).where(InfluencerImage.is_primary == True))
        for img in result.scalars().all():
            img.is_primary = False
    
    # Create record
    image = InfluencerImage(
        filename=filename,
        original_name=file.filename,
        is_primary=is_primary
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
    
    # Update .env file
    set_key(str(ENV_PATH), "COMFYUI_URL", comfyui_url.strip())
    
    # Update runtime config
    app_settings.comfyui_url = comfyui_url.strip()
    
    return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)


