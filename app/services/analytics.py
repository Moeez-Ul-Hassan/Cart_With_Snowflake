import structlog

logger = structlog.get_logger()

def track_cart_event(user_id: int, event_type: str, product_id: int = None, quantity: int = None):
    """
    Mock service to simulate sending event data to AWS Kinesis or another event bus.
    """
    event_payload = {
        "user_id": user_id,
        "event_type": event_type,
        "product_id": product_id,
        "quantity": quantity
    }
    logger.info("kinesis_event_dispatched", **event_payload)