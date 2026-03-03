"""Stripe billing and subscription endpoints."""
import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.future import select
import structlog
from datetime import datetime

from app.config import settings
from app.services.auth import get_current_user
from app.services.database import async_session
from app.models.database import Subscription, StripeEventIdempotency
from app.models.schemas import SubscriptionStatusResponse
from app.services.passport import passport_admin

logger = structlog.get_logger()
stripe.api_key = settings.STRIPE_SECRET_KEY

router = APIRouter()

@router.post("/create-checkout-session")
async def create_checkout_session(user=Depends(get_current_user)):
    """Create a Stripe checkout session to purchase Aether Audio Pro."""
    user_id = user.get("sub")
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found in token.")

    try:
        checkout_session = stripe.checkout.Session.create(
            line_items=[
                {
                    "price": settings.PRO_TIER_PRICE_ID,
                    "quantity": 1,
                },
            ],
            mode="subscription",
            success_url=settings.STRIPE_SUCCESS_URL + "?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=settings.STRIPE_CANCEL_URL,
            # Extremely important: Bind the Stripe checkout strictly to this Passport ID
            client_reference_id=user_id,
        )
    except Exception as e:
        logger.error("stripe_checkout_failed", error=str(e), user_id=user_id)
        raise HTTPException(status_code=500, detail=str(e))

    return {"url": checkout_session.url}


@router.post("/create-portal-session")
async def create_portal_session(user=Depends(get_current_user)):
    """Create a Stripe Billing Portal session for the user to manage their subscription."""
    user_id = user.get("sub")
    
    async with async_session() as session:
        result = await session.execute(
            select(Subscription).where(Subscription.passport_user_id == user_id)
        )
        subscription_obj = result.scalars().first()
        
    if not subscription_obj or not subscription_obj.stripe_customer_id:
        raise HTTPException(status_code=404, detail="No active Stripe customer found for this user.")

    try:
        portal_session = stripe.billing_portal.Session.create(
            customer=subscription_obj.stripe_customer_id,
            return_url=settings.STRIPE_CANCEL_URL, # Returns them to the dashboard/cancel page
        )
        return {"url": portal_session.url}
    except Exception as e:
        logger.error("stripe_portal_failed", error=str(e), user_id=user_id)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/success")
async def payment_success(session_id: str):
    """Handle successful checkout return."""
    # The frontend could intercept this or we can redirect to the UI's dashboard
    return RedirectResponse(url="/")


@router.get("/cancel")
async def payment_cancel():
    """Handle canceled checkout return."""
    return RedirectResponse(url="/")


@router.get("/status", response_model=SubscriptionStatusResponse)
async def get_subscription_status(user=Depends(get_current_user)):
    """Get the current subscription status from the database."""
    user_id = user.get("sub")
    async with async_session() as session:
        result = await session.execute(
            select(Subscription).where(Subscription.passport_user_id == user_id)
        )
        subscription_obj = result.scalars().first()
        
    if not subscription_obj:
        return SubscriptionStatusResponse(
            passport_user_id=user_id,
            status="inactive",
            tier="Free"
        )
        
    return SubscriptionStatusResponse(
        passport_user_id=user_id,
        stripe_subscription_id=subscription_obj.stripe_subscription_id,
        status=subscription_obj.status,
        current_period_end=subscription_obj.current_period_end,
        tier="Aether Audio Pro"
    )

@router.post("/webhook")
async def stripe_webhook(request: Request):
    """Authoritative Stripe Webhook endpoint strictly mapped to Passport-IAM."""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    
    if not sig_header:
        raise HTTPException(status_code=400, detail="Missing signature header")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError as e:
        logger.error("invalid_stripe_payload", error=str(e))
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError as e:
        logger.error("invalid_stripe_signature", error=str(e))
        raise HTTPException(status_code=400, detail="Invalid signature")

    event_id = event["id"]
    event_type = event["type"]

    async with async_session() as db_session:
        # 1. Idempotency Check
        idempotency_result = await db_session.execute(
            select(StripeEventIdempotency).where(StripeEventIdempotency.event_id == event_id)
        )
        if idempotency_result.scalars().first():
            logger.info("stripe_webhook_idempotency_skip", event_id=event_id)
            return {"status": "success", "message": "Already processed"}

        db_session.add(StripeEventIdempotency(event_id=event_id))
        await db_session.commit()

        # 2. Process specific events
        try:
            if event_type == "checkout.session.completed":
                session = event["data"]["object"]
                passport_user_id = session.get("client_reference_id")
                customer_id = session.get("customer")
                subscription_id = session.get("subscription")
                
                if passport_user_id and customer_id and subscription_id:
                    # Upsert DB Row
                    sub_result = await db_session.execute(
                        select(Subscription).where(Subscription.passport_user_id == passport_user_id)
                    )
                    db_sub = sub_result.scalars().first()
                    
                    stripe_sub = stripe.Subscription.retrieve(subscription_id)
                    period_end = datetime.fromtimestamp(stripe_sub.current_period_end)
                    
                    if not db_sub:
                        db_sub = Subscription(
                            passport_user_id=passport_user_id,
                            stripe_customer_id=customer_id,
                            stripe_subscription_id=subscription_id,
                            status=stripe_sub.status,
                            current_period_end=period_end
                        )
                        db_session.add(db_sub)
                    else:
                        db_sub.stripe_customer_id = customer_id
                        db_sub.stripe_subscription_id = subscription_id
                        db_sub.status = stripe_sub.status
                        db_sub.current_period_end = period_end
                    
                    await db_session.commit()
                    
                    # Assign realm role in Passport
                    await passport_admin.assign_realm_role(passport_user_id, "pro_audio")

            elif event_type in ["customer.subscription.updated", "customer.subscription.created"]:
                subscription = event["data"]["object"]
                subscription_id = subscription.get("id")
                status_str = subscription.get("status")
                period_end = datetime.fromtimestamp(subscription.get("current_period_end"))
                
                sub_result = await db_session.execute(
                    select(Subscription).where(Subscription.stripe_subscription_id == subscription_id)
                )
                db_sub = sub_result.scalars().first()
                
                if db_sub:
                    db_sub.status = status_str
                    db_sub.current_period_end = period_end
                    await db_session.commit()
                    
                    # Ensure alignment of role
                    if status_str in ["active", "trialing"]:
                        await passport_admin.assign_realm_role(db_sub.passport_user_id, "pro_audio")
                    elif status_str in ["canceled", "unpaid"]:
                        await passport_admin.remove_realm_role(db_sub.passport_user_id, "pro_audio")

            elif event_type == "customer.subscription.deleted":
                subscription = event["data"]["object"]
                subscription_id = subscription.get("id")
                
                sub_result = await db_session.execute(
                    select(Subscription).where(Subscription.stripe_subscription_id == subscription_id)
                )
                db_sub = sub_result.scalars().first()
                if db_sub:
                    db_sub.status = "canceled"
                    await db_session.commit()
                    # Remove realm role in Passport
                    await passport_admin.remove_realm_role(db_sub.passport_user_id, "pro_audio")
                    
            elif event_type == "invoice.payment_failed":
                invoice = event["data"]["object"]
                subscription_id = invoice.get("subscription")
                if subscription_id:
                    sub_result = await db_session.execute(
                        select(Subscription).where(Subscription.stripe_subscription_id == subscription_id)
                    )
                    db_sub = sub_result.scalars().first()
                    if db_sub:
                        db_sub.status = "past_due"
                        await db_session.commit()
                        # User policy: do not remove role immediately (grace period implicitly enforced by not calling Admin API removing role)

        except Exception as e:
            logger.error("stripe_webhook_processing_error", error=str(e), event_id=event_id)
            # We don't raise 500 otherwise Stripe will keep retrying and fill logs until fixed.
            # In production, we'd queue this to a DLQ or re-raise if we explicitly want retries.

    return {"status": "success"}
