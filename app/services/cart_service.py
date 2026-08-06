from sqlalchemy.orm import Session
from redis import Redis
from app.models.domain import Cart
from app.exceptions.business_logic import CartNotFoundException, CartNotActiveException
from app.services.aws_sqs import send_event_to_sqs
import structlog

logger = structlog.get_logger()

class CartService:
    def __init__(self, db: Session, cache: Redis):
        self.db = db
        self.cache = cache

    def checkout_cart(self, cart_id: int, idempotency_key: str):
        # 1. Existing Idempotency Check
        if self.cache.get(idempotency_key):
            logger.info("idempotent_request_intercepted", cart_id=cart_id, key=idempotency_key)
            return {"status": "success", "message": "Order was already placed successfully. (Cached)"}

        # 2. Existing DB Validation
        cart = self.db.query(Cart).filter(Cart.id == cart_id).first()
        if not cart:
            raise CartNotFoundException(cart_id=cart_id)
        if cart.status != "active":
            raise CartNotActiveException(cart_id=cart_id, current_status=cart.status)

        # 3. DB Transaction
        cart.status = "checked_out"
        self.db.commit()

        # 4. Redis Cache Set
        self.cache.set(idempotency_key, "processed", ex=86400)
        logger.info("cart_checked_out", cart.id, idempotency_key=idempotency_key)

        # 5. Publish CHECKOUT Business Event
        checkout_payload = {
            "cart_id": cart.id,
            "user_id": cart.user_id,
            "total_amount": float(cart.total_amount) if hasattr(cart, 'total_amount') and cart.total_amount else 0.0,
            "status": cart.status
        }
        send_event_to_sqs(event_type="CHECKOUT", data=checkout_payload, domain="cart")

        return {"status": "success", "message": "Order placed successfully"}

    def add_item_to_cart(self, cart_id: int, user_id: int, product_id: int, quantity: int, price: float):
        """
        Example pattern for publishing ITEM_ADDED events alongside DB additions.
        """
        # [Existing DB Item Add Logic Here...]
        
        # Publish Event
        item_payload = {
            "cart_id": cart_id,
            "user_id": user_id,
            "product_id": product_id,
            "quantity": quantity,
            "price_at_addition": price
        }
        send_event_to_sqs(event_type="ITEM_ADDED", data=item_payload, domain="cart")