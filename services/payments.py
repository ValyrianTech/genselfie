"""Payment services for Stripe and LNbits (Lightning Network)."""

from typing import Optional
import httpx

from config import settings


# ============================================================================
# Stripe Integration
# ============================================================================

async def create_stripe_payment(amount_cents: int, currency: str) -> dict:
    """Create a Stripe PaymentIntent.
    
    Args:
        amount_cents: Amount in smallest currency unit (cents for USD)
        currency: Three-letter currency code (e.g., 'USD')
    
    Returns:
        Dict with client_secret and payment_intent_id
    """
    if not settings.stripe_secret_key:
        return {"error": "Stripe not configured"}
    
    try:
        import stripe
        stripe.api_key = settings.stripe_secret_key
        
        intent = stripe.PaymentIntent.create(
            amount=amount_cents,
            currency=currency.lower(),
            automatic_payment_methods={"enabled": True},
        )
        
        return {
            "client_secret": intent.client_secret,
            "payment_intent_id": intent.id,
            "publishable_key": settings.stripe_publishable_key
        }
    except Exception as e:
        return {"error": str(e)}


async def check_stripe_payment(payment_intent_id: str) -> dict:
    """Check the status of a Stripe PaymentIntent.
    
    Args:
        payment_intent_id: The PaymentIntent ID to check
    
    Returns:
        Dict with 'paid' boolean and status info
    """
    if not settings.stripe_secret_key:
        return {"error": "Stripe not configured", "paid": False}
    
    try:
        import stripe
        stripe.api_key = settings.stripe_secret_key
        
        intent = stripe.PaymentIntent.retrieve(payment_intent_id)
        
        return {
            "paid": intent.status == "succeeded",
            "status": intent.status
        }
    except Exception as e:
        return {"error": str(e), "paid": False}


# ============================================================================
# LNbits (Lightning Network) Integration
# ============================================================================

async def create_lightning_invoice(amount_cents: int, currency: str) -> dict:
    """Create a Lightning invoice via LNbits.
    
    Args:
        amount_cents: Amount in cents (will be converted to sats)
        currency: Currency code (used for conversion if not BTC)
    
    Returns:
        Dict with payment_request (invoice), payment_hash, and checking_id
    """
    if not settings.lnbits_url or not settings.lnbits_api_key:
        return {"error": "LNbits not configured"}
    
    # Convert cents to satoshis (rough conversion, should use real exchange rate)
    # For now, assume 1 USD = 100 cents = ~2500 sats (adjust based on BTC price)
    # In production, you'd want to fetch the current exchange rate
    if currency.upper() == "USD":
        amount_sats = int(amount_cents * 25)  # Rough estimate: $1 = 2500 sats
    else:
        amount_sats = amount_cents  # Assume already in sats if not USD
    
    # Minimum 1 sat
    amount_sats = max(1, amount_sats)
    
    url = f"{settings.lnbits_url}/api/v1/payments"
    headers = {
        "X-Api-Key": settings.lnbits_api_key,
        "Content-Type": "application/json"
    }
    payload = {
        "out": False,  # Incoming payment (invoice)
        "amount": amount_sats,
        "memo": "GenSelfie Generation",
        "unit": "sat"
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=payload, headers=headers, timeout=30.0)
            
            if response.status_code == 201:
                data = response.json()
                return {
                    "payment_request": data.get("payment_request"),
                    "payment_hash": data.get("payment_hash"),
                    "checking_id": data.get("checking_id"),
                    "amount_sats": amount_sats
                }
            else:
                return {"error": f"LNbits error: {response.status_code}"}
        except httpx.RequestError as e:
            return {"error": str(e)}


async def check_lightning_payment(checking_id: str) -> dict:
    """Check if a Lightning invoice has been paid.
    
    Args:
        checking_id: The checking_id from the invoice creation
    
    Returns:
        Dict with 'paid' boolean
    """
    if not settings.lnbits_url or not settings.lnbits_api_key:
        return {"error": "LNbits not configured", "paid": False}
    
    url = f"{settings.lnbits_url}/api/v1/payments/{checking_id}"
    headers = {
        "X-Api-Key": settings.lnbits_api_key
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers, timeout=10.0)
            
            if response.status_code == 200:
                data = response.json()
                return {"paid": data.get("paid", False)}
            else:
                return {"paid": False}
        except httpx.RequestError:
            return {"paid": False}


# ============================================================================
# Unified Payment Interface
# ============================================================================

async def create_payment(payment_type: str, amount_cents: int, currency: str) -> dict:
    """Create a payment of the specified type.
    
    Args:
        payment_type: 'stripe' or 'lightning'
        amount_cents: Amount in cents
        currency: Currency code
    
    Returns:
        Payment creation result
    """
    if payment_type == "stripe":
        return await create_stripe_payment(amount_cents, currency)
    elif payment_type == "lightning":
        return await create_lightning_invoice(amount_cents, currency)
    else:
        return {"error": f"Unknown payment type: {payment_type}"}


async def check_payment_status(payment_type: str, payment_id: str) -> dict:
    """Check the status of a payment.
    
    Args:
        payment_type: 'stripe' or 'lightning'
        payment_id: The payment/invoice ID
    
    Returns:
        Dict with 'paid' boolean and additional status info
    """
    if payment_type == "stripe":
        return await check_stripe_payment(payment_id)
    elif payment_type == "lightning":
        return await check_lightning_payment(payment_id)
    else:
        return {"error": f"Unknown payment type: {payment_type}", "paid": False}
