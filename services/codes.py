"""Promo code validation and consumption service."""

from datetime import datetime
from typing import Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import PromoCode


async def validate_and_consume_code(db: AsyncSession, code: str) -> Tuple[bool, str]:
    """Validate a promo code and consume one use if valid.
    
    Args:
        db: Database session
        code: The promo code to validate
    
    Returns:
        Tuple of (success, error_message)
    """
    code = code.upper().strip()
    
    result = await db.execute(
        select(PromoCode)
        .where(PromoCode.code == code)
        .where(PromoCode.is_active == True)
    )
    promo = result.scalar_one_or_none()
    
    if not promo:
        return False, "Invalid promo code"
    
    # Check uses remaining
    if promo.uses_remaining is not None and promo.uses_remaining <= 0:
        return False, "This code has been fully used"
    
    # Check expiry
    if promo.expires_at and promo.expires_at < datetime.utcnow():
        return False, "This code has expired"
    
    # Consume one use
    if promo.uses_remaining is not None:
        promo.uses_remaining -= 1
    
    await db.commit()
    
    return True, ""


async def get_code_info(db: AsyncSession, code: str) -> dict:
    """Get information about a promo code without consuming it."""
    code = code.upper().strip()
    
    result = await db.execute(
        select(PromoCode)
        .where(PromoCode.code == code)
        .where(PromoCode.is_active == True)
    )
    promo = result.scalar_one_or_none()
    
    if not promo:
        return {"valid": False, "error": "Invalid code"}
    
    if promo.uses_remaining is not None and promo.uses_remaining <= 0:
        return {"valid": False, "error": "Code fully used"}
    
    if promo.expires_at and promo.expires_at < datetime.utcnow():
        return {"valid": False, "error": "Code expired"}
    
    return {
        "valid": True,
        "uses_remaining": promo.uses_remaining,
        "expires_at": promo.expires_at.isoformat() if promo.expires_at else None
    }
