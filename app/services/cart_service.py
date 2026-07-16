from sqlalchemy.orm import Session
from redis import Redis
from app.models.domain import Cart
from app.exceptions.business_logic import CartNotFoundException, CartNotActiveException
import structlog

logger = structlog.get_logger()

class CartService:
    def __init__(self, db: Session, cache: Redis):
        self.db = db
        self.cache = cache

    def checkout_cart(self, cart_id: int, idempotency_key: str):
        if self.cache.get(idempotency_key):
            logger.info("idempotent_request_intercepted", cart_id=cart_id, key=idempotency_key)
            return {"status": "success", "message": "Order was already placed successfully. (Cached)"}

        cart = self.db.query(Cart).filter(Cart.id == cart_id).first()
        if not cart:
            raise CartNotFoundException(cart_id=cart_id)
        if cart.status != "active":
            raise CartNotActiveException(cart_id=cart_id, current_status=cart.status)

        cart.status = "checked_out"
        self.db.commit()

        self.cache.set(idempotency_key, "processed", ex=86400)
        logger.info("cart_checked_out", cart_id=cart.id, idempotency_key=idempotency_key)
        return {"status": "success", "message": "Order placed successfully"}