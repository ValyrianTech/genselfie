from typing import Optional
from pathlib import Path
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings as app_settings
from database import get_db, Settings, InfluencerImage, Generation, PromoCode
from services.social import fetch_profile_image
from services.codes import validate_and_consume_code
from services.comfyui import generate_selfie, get_generation_status, get_queue_status
from services.payments import create_stripe_payment, create_lightning_invoice, check_payment_status

router = APIRouter(tags=["public"])
templates = Jinja2Templates(directory="templates")


def get_example_images_from_disk() -> list[dict]:
    """Get example images directly from the generated directory."""
    generated_dir = app_settings.upload_dir / "generated"
    examples = []
    
    if generated_dir.exists():
        for img_path in sorted(generated_dir.glob("*.png"), key=lambda p: p.stat().st_mtime, reverse=True):
            examples.append({
                "url": f"/static/uploads/generated/{img_path.name}",
                "name": img_path.stem
            })
    
    return examples


@router.get("/", response_class=HTMLResponse)
async def home(request: Request, db: AsyncSession = Depends(get_db)):
    """Main fan-facing page."""
    # Get settings
    settings = await db.get(Settings, 1)
    
    # Get example images from disk
    examples = get_example_images_from_disk()
    
    return templates.TemplateResponse("index.html", {
        "request": request,
        "settings": settings,
        "examples": examples,
    })


@router.get("/api/server-status")
async def server_status():
    """Check ComfyUI server status and queue size."""
    import httpx
    
    # Directly check if ComfyUI is reachable
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{app_settings.comfyui_url}/queue",
                timeout=5.0
            )
            if response.status_code == 200:
                queue = response.json()
                pending = len(queue.get("queue_pending", []))
                running = len(queue.get("queue_running", []))
                
                return JSONResponse({
                    "online": True,
                    "queue_pending": pending,
                    "queue_running": running,
                    "queue_total": pending + running
                })
    except Exception:
        pass
    
    return JSONResponse({
        "online": False,
        "queue_pending": 0,
        "queue_running": 0,
        "queue_total": 0
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
    payment_type: str = Form(...),  # stripe or lightning
    db: AsyncSession = Depends(get_db)
):
    """Create a payment intent or lightning invoice."""
    settings = await db.get(Settings, 1)
    
    if payment_type == "stripe":
        if not settings.stripe_enabled:
            raise HTTPException(status_code=400, detail="Stripe payments not enabled")
        result = await create_stripe_payment(settings.price_cents, settings.currency)
        return JSONResponse(result)
    
    elif payment_type == "lightning":
        if not settings.lightning_enabled:
            raise HTTPException(status_code=400, detail="Lightning payments not enabled")
        result = await create_lightning_invoice(settings.price_cents, settings.currency)
        return JSONResponse(result)
    
    raise HTTPException(status_code=400, detail="Invalid payment type")


@router.get("/api/payment-status/{payment_id}")
async def payment_status(payment_id: str, payment_type: str):
    """Check payment status."""
    result = await check_payment_status(payment_type, payment_id)
    return JSONResponse(result)


@router.post("/api/generate")
async def generate(
    request: Request,
    payment_method: str = Form(...),  # code, stripe, lightning
    payment_id: Optional[str] = Form(None),
    promo_code: Optional[str] = Form(None),
    platform: Optional[str] = Form(None),
    handle: Optional[str] = Form(None),
    uploaded_image: Optional[UploadFile] = File(None),
    db: AsyncSession = Depends(get_db)
):
    """Generate a selfie after payment verification."""
    settings = await db.get(Settings, 1)
    
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
    import uuid
    fan_image_url = None
    fan_image_path = None  # Filesystem path for ComfyUI
    
    if uploaded_image and uploaded_image.filename:
        # Save uploaded image temporarily
        ext = uploaded_image.filename.split(".")[-1]
        filename = f"fan_{uuid.uuid4().hex}.{ext}"
        filepath = app_settings.upload_dir / filename
        content = await uploaded_image.read()
        with open(filepath, "wb") as f:
            f.write(content)
        fan_image_url = f"/static/uploads/{filename}"
        fan_image_path = str(filepath)
    elif platform and handle:
        fan_image_url = await fetch_profile_image(platform, handle)
        fan_image_path = fan_image_url  # URL for social media images
    
    if not fan_image_url:
        raise HTTPException(status_code=400, detail="No fan image provided")
    
    # Get influencer images
    result = await db.execute(
        select(InfluencerImage).order_by(InfluencerImage.is_primary.desc())
    )
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
    
    # Start generation
    try:
        prompt_id = await generate_selfie(
            fan_image_url=fan_image_path,
            influencer_images=[img.filename for img in influencer_images]
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
        return JSONResponse({"status": "failed"})
    
    if generation.prompt_id:
        # Check ComfyUI status
        result = await get_generation_status(generation.prompt_id)
        if result.get("completed"):
            generation.status = "completed"
            generation.result_image_url = result.get("image_url")
            from datetime import datetime
            generation.completed_at = datetime.utcnow()
            await db.commit()
            return JSONResponse({
                "status": "completed",
                "result_url": generation.result_image_url
            })
    
    return JSONResponse({"status": generation.status})
