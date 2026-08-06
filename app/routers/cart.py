from fastapi import APIRouter, Depends, Header, Path, Query, BackgroundTasks
from sqlalchemy.orm import Session
from redis import Redis
import structlog

from app.database.session import get_db
from app.database.redis_client import get_redis
from app.services.cart_service import CartService
# Import the SQS Streaming Service
from app.services.aws_sqs import send_event_to_sqs 
from app.schemas.domain import CartResponse, CartItemCreate, BillResponse
from app.models.domain import Cart, CartItem, Product
from app.exceptions.business_logic import (
    ProductNotFoundException, CartNotFoundException,
    InsufficientStockException, CartNotActiveException,
    ItemNotFoundInCartException
)

logger = structlog.get_logger()
router = APIRouter()

@router.post("/", response_model=CartResponse)
def create_cart(
    background_tasks: BackgroundTasks,  # <-- Added BackgroundTasks here
    user_id: int = Query(..., gt=0, description="User ID must be positive"),
    db: Session = Depends(get_db)
):
    existing_cart = db.query(Cart).filter(
        Cart.user_id == user_id,
        Cart.status == "active",
        Cart.is_deleted.is_(False)
    ).first()
    
    if existing_cart:
        return existing_cart

    new_cart = Cart(user_id=user_id, status="active", total_amount=0.0)
    db.add(new_cart)
    db.commit()
    db.refresh(new_cart)
    
    # PHASE 2: Stream event to SQS
    event_data = {
        "cart_id": new_cart.id,
        "user_id": new_cart.user_id,
        "status": new_cart.status
    }
    background_tasks.add_task(send_event_to_sqs, "CART_CREATED", event_data, "cart")
    
    logger.info("cart_created", cart_id=new_cart.id, user_id=user_id)
    return new_cart

@router.post("/{cart_id}/items", response_model=CartResponse)
def add_item_to_cart(
    item: CartItemCreate, 
    background_tasks: BackgroundTasks,
    cart_id: int = Path(..., gt=0, description="Cart ID must be positive"), 
    db: Session = Depends(get_db)
):
    cart = db.query(Cart).filter(Cart.id == cart_id).first()
    if not cart:
        raise CartNotFoundException(cart_id=cart_id)
    if cart.status != "active":
        raise CartNotActiveException(cart_id=cart_id, current_status=cart.status)

    product = db.query(Product).filter(Product.id == item.product_id).first()
    if not product:
        raise ProductNotFoundException(product_id=item.product_id)

    available_stock = product.stock - product.reserved_stock
    if available_stock < item.quantity:
        raise InsufficientStockException(
            product_id=product.id, requested_qty=item.quantity, available_qty=available_stock
        )

    cart_item = CartItem(
        cart_id=cart.id, product_id=product.id, quantity=item.quantity, price_at_addition=product.price
    )
    cart.total_amount += (product.price * item.quantity)
    product.reserved_stock += item.quantity
    
    db.add(cart_item)
    db.commit()
    db.refresh(cart)

    # PHASE 2: Stream event to SQS
    event_data = {
        "user_id": cart.user_id, 
        "cart_id": cart.id, 
        "product_id": product.id, 
        "quantity": item.quantity,
        "price_at_addition": product.price
    }
    # Corrected event name to uppercase ITEM_ADDED
    background_tasks.add_task(send_event_to_sqs, "ITEM_ADDED", event_data, "cart")
    
    logger.info("item_added", cart_id=cart.id, product_id=product.id, quantity=item.quantity)
    return cart

@router.post("/{cart_id}/checkout")
def checkout_cart(
    background_tasks: BackgroundTasks,
    cart_id: int = Path(..., gt=0),
    x_idempotency_key: str = Header(...),
    db: Session = Depends(get_db),
    cache: Redis = Depends(get_redis)
):
    service = CartService(db=db, cache=cache)
    response = service.checkout_cart(cart_id=cart_id, idempotency_key=x_idempotency_key)

    cart = db.query(Cart).filter(Cart.id == cart_id).first()
    if cart:
        # PHASE 2: Stream event to SQS
        event_data = {"user_id": cart.user_id, "cart_id": cart.id, "total_amount": float(cart.total_amount)}
        # Corrected event name to uppercase CHECKOUT
        background_tasks.add_task(send_event_to_sqs, "CHECKOUT", event_data, "cart")
        
    return response

@router.get("/{cart_id}", response_model=CartResponse)
def get_cart(cart_id: int = Path(..., gt=0), db: Session = Depends(get_db)):
    cart = db.query(Cart).filter(Cart.id == cart_id).first()
    if not cart:
        raise CartNotFoundException(cart_id=cart_id)

    actual_total = sum(item.price_at_addition * item.quantity for item in cart.items)
    if cart.total_amount != actual_total:
        cart.total_amount = actual_total
        db.commit()
        db.refresh(cart)
        
    return cart

@router.delete("/{cart_id}/items/{product_id}", response_model=CartResponse)
def remove_item_from_cart(
    background_tasks: BackgroundTasks,
    cart_id: int = Path(..., gt=0),
    product_id: int = Path(..., gt=0),
    db: Session = Depends(get_db)
):
    cart = db.query(Cart).filter(Cart.id == cart_id).first()
    if not cart:
        raise CartNotFoundException(cart_id=cart_id)
    if cart.status != "active":
        raise CartNotActiveException(cart_id=cart_id, current_status=cart.status)

    cart_item = db.query(CartItem).filter(CartItem.cart_id == cart_id, CartItem.product_id == product_id).first()
    if not cart_item:
        raise ItemNotFoundInCartException(cart_id=cart_id, product_id=product_id)

    product = db.query(Product).filter(Product.id == product_id).first()

    cart.total_amount -= (cart_item.price_at_addition * cart_item.quantity)
    product.reserved_stock -= cart_item.quantity
    quantity_removed = cart_item.quantity
    
    db.delete(cart_item)
    db.commit()
    db.refresh(cart)

    # PHASE 2: Stream event to SQS
    event_data = {
        "user_id": cart.user_id, 
        "cart_id": cart.id, 
        "product_id": product.id, 
        "quantity": quantity_removed
    }
    # Corrected event name to uppercase ITEM_REMOVED
    background_tasks.add_task(send_event_to_sqs, "ITEM_REMOVED", event_data, "cart")
    
    logger.info("item_removed", cart_id=cart.id, product_id=product.id)
    return cart

@router.get("/{cart_id}/bill", response_model=BillResponse)
def generate_bill(cart_id: int = Path(..., gt=0), db: Session = Depends(get_db)):
    cart = db.query(Cart).filter(Cart.id == cart_id).first()
    if not cart:
        raise CartNotFoundException(cart_id=cart_id)

    actual_subtotal = sum(item.price_at_addition * item.quantity for item in cart.items)
    tax_rate = 0.0
    tax_amount = round(actual_subtotal * tax_rate, 2)
    grand_total = round(actual_subtotal + tax_amount, 2)

    if cart.total_amount != actual_subtotal:
        cart.total_amount = actual_subtotal
        db.commit()
        
    logger.info("bill_generated", cart_id=cart.id, grand_total=grand_total)
    return BillResponse(
        cart_id=cart.id, subtotal=round(actual_subtotal, 2), tax_amount=tax_amount, grand_total=grand_total
    )

@router.delete("/{cart_id}")
def abandon_cart(
    background_tasks: BackgroundTasks,
    cart_id: int = Path(..., gt=0),
    db: Session = Depends(get_db)
):
    cart = db.query(Cart).filter(Cart.id == cart_id).first()
    if not cart:
        raise CartNotFoundException(cart_id=cart_id)
    if cart.status != "active":
        raise CartNotActiveException(cart_id=cart_id, current_status=cart.status)

    for item in cart.items:
        product = db.query(Product).filter(Product.id == item.product_id).first()
        if product:
            product.reserved_stock -= item.quantity

    cart.status = "abandoned"
    cart.is_deleted = True
    db.commit()

    # PHASE 2: Stream event to SQS
    event_data = {"user_id": cart.user_id, "cart_id": cart.id}
    # Corrected event name to uppercase CART_ABANDONED
    background_tasks.add_task(send_event_to_sqs, "CART_ABANDONED", event_data, "cart")
    
    logger.info("cart_abandoned", cart_id=cart.id)
    return {"status": "success", "message": "Cart abandoned and inventory released"}