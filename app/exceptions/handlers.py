from fastapi import Request, status
from fastapi.responses import JSONResponse
import structlog
from app.exceptions.business_logic import (
    ProductNotFoundException, CartNotFoundException,
    InsufficientStockException, CartNotActiveException,
    ItemNotFoundInCartException
)

logger = structlog.get_logger()

async def product_not_found_handler(request: Request, exc: ProductNotFoundException):
    logger.warning("product_not_found_error", product_id=exc.product_id, path=request.url.path)
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"error_code": "PRODUCT_NOT_FOUND", "message": f"Product with ID {exc.product_id} does not exist in the catalog."}
    )

async def item_not_found_handler(request: Request, exc: ItemNotFoundInCartException):
    logger.warning("item_not_in_cart_error", cart_id=exc.cart_id, product_id=exc.product_id)
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"error_code": "ITEM_NOT_IN_CART", "message": f"Product {exc.product_id} is not in Cart {exc.cart_id}."}
    )

async def cart_not_found_handler(request: Request, exc: CartNotFoundException):
    logger.warning("cart_not_found_error", cart_id=exc.cart_id, path=request.url.path)
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"error_code": "CART_NOT_FOUND", "message": f"Cart with ID {exc.cart_id} could not be found."}
    )

async def insufficient_stock_handler(request: Request, exc: InsufficientStockException):
    logger.warning("insufficient_stock_error", product_id=exc.product_id, requested=exc.requested_qty)
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"error_code": "INSUFFICIENT_STOCK", "message": f"Cannot add {exc.requested_qty} of product {exc.product_id}. Only {exc.available_qty} available."}
    )

async def cart_not_active_handler(request: Request, exc: CartNotActiveException):
    logger.warning("cart_not_active_error", cart_id=exc.cart_id, status=exc.current_status)
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"error_code": "CART_NOT_ACTIVE", "message": f"Action rejected. Cart {exc.cart_id} is currently '{exc.current_status}'."}
    )