class CartAPIException(Exception):
    pass

class ProductNotFoundException(CartAPIException):
    def __init__(self, product_id: int):
        self.product_id = product_id

class CartNotFoundException(CartAPIException):
    def __init__(self, cart_id: int):
        self.cart_id = cart_id

class InsufficientStockException(CartAPIException):
    def __init__(self, product_id: int, requested_qty: int, available_qty: int):
        self.product_id = product_id
        self.requested_qty = requested_qty
        self.available_qty = available_qty

class CartNotActiveException(CartAPIException):
    def __init__(self, cart_id: int, current_status: str):
        self.cart_id = cart_id
        self.current_status = current_status

class ItemNotFoundInCartException(CartAPIException):
    def __init__(self, cart_id: int, product_id: int):
        self.cart_id = cart_id
        self.product_id = product_id