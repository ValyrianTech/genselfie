from datetime import datetime
from typing import Optional
from sqlalchemy import Boolean, DateTime, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from config import settings


class Base(DeclarativeBase):
    pass


class Settings(Base):
    """App settings - single row table."""
    __tablename__ = "settings"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    app_name: Mapped[str] = mapped_column(String(255), default="GenSelfie")
    tagline: Mapped[str] = mapped_column(String(500), default="Get a selfie with your favorite influencer!")
    banner_image: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    logo_image: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    primary_color: Mapped[str] = mapped_column(String(7), default="#6366f1")
    secondary_color: Mapped[str] = mapped_column(String(7), default="#8b5cf6")
    
    # Currency (pricing is per-preset)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    
    # Payment toggles
    stripe_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    lightning_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    codes_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Failsafe: auto-generate promo code on failed generation
    failsafe_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # ComfyUI workflow
    workflow_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class InfluencerImage(Base):
    """Reference images of the influencer for AI generation."""
    __tablename__ = "influencer_images"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    filename: Mapped[str] = mapped_column(String(500))
    original_name: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PromoCode(Base):
    """Promo codes for free/discounted generations."""
    __tablename__ = "promo_codes"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    uses_remaining: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # None = unlimited
    max_uses: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Generation(Base):
    """Record of each generated selfie."""
    __tablename__ = "generations"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    fan_image_url: Mapped[str] = mapped_column(String(1000))  # Input image URL or path
    fan_platform: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # twitter, bluesky, etc.
    fan_handle: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    result_image_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    prompt_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # ComfyUI prompt ID
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending, processing, completed, failed
    payment_method: Mapped[str] = mapped_column(String(20))  # code, stripe, lightning
    promo_code_used: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    payment_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    retry_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # Failsafe code if generation failed
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class Preset(Base):
    """Generation presets combining influencer image, dimensions, and prompt."""
    __tablename__ = "presets"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255))  # e.g., "Close-up Selfie", "Full Body"
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    influencer_image_id: Mapped[int] = mapped_column(Integer)  # FK to influencer_images
    width: Mapped[int] = mapped_column(Integer, default=1024)
    height: Mapped[int] = mapped_column(Integer, default=1024)
    prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Custom prompt for this preset
    price_cents: Mapped[int] = mapped_column(Integer, default=500)  # Price in cents for this preset
    allow_prompt_edit: Mapped[bool] = mapped_column(Boolean, default=False)  # Allow fan to edit prompt
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ExampleInput(Base):
    """Input images for generating example selfies (e.g., celebrity images)."""
    __tablename__ = "example_inputs"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    filename: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ExampleImage(Base):
    """Pre-generated example selfies with celebrities."""
    __tablename__ = "example_images"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    example_input_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    celebrity_name: Mapped[str] = mapped_column(String(255))
    input_image_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    result_image_url: Mapped[str] = mapped_column(String(1000))
    prompt_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    is_visible: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Payment(Base):
    """Payment records for Stripe and Lightning."""
    __tablename__ = "payments"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    payment_type: Mapped[str] = mapped_column(String(20))  # stripe, lightning
    external_id: Mapped[str] = mapped_column(String(255))  # Stripe payment intent ID or LNbits invoice ID
    amount_cents: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3))
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending, completed, failed
    generation_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


# Async engine and session
engine = create_async_engine(settings.database_url, echo=settings.debug)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db():
    """Initialize database and create tables."""
    import shutil
    from pathlib import Path
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Ensure settings row exists
    async with async_session() as session:
        result = await session.get(Settings, 1)
        if not result:
            session.add(Settings(id=1))
            await session.commit()
        
        # Import example inputs from input_examples/ if none exist
        from sqlalchemy import select
        result = await session.execute(select(ExampleInput))
        if not result.scalars().first():
            input_examples_dir = settings.base_dir / "input_examples"
            examples_upload_dir = settings.upload_dir / "examples"
            examples_upload_dir.mkdir(exist_ok=True)
            
            if input_examples_dir.exists():
                image_extensions = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp")
                for img_path in [p for p in input_examples_dir.iterdir() if p.suffix.lower() in image_extensions]:
                    # Copy to uploads/examples
                    dest_path = examples_upload_dir / img_path.name
                    shutil.copy(img_path, dest_path)
                    
                    # Create database record
                    name = img_path.stem  # Filename without extension
                    example = ExampleInput(name=name, filename=img_path.name)
                    session.add(example)
                
                await session.commit()


async def get_db() -> AsyncSession:
    """Dependency for getting database session."""
    async with async_session() as session:
        yield session
