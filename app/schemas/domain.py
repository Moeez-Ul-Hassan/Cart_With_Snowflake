from pydantic import BaseModel, Field, ConfigDict
from typing import List

class ProductBase(BaseModel):
    name: str
    price: float
    stock: int

class ProductResponse(ProductBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

class CartItemCreate(BaseModel):
    product_id: int = Field(gt=0, description="Product ID must be valid")
    quantity: int = Field(gt=0, description="Quantity must be at least 1")

class CartItemUpdate(BaseModel):
    quantity: int = Field(gt=0, description="The new total quantity for this item")

class CartItemResponse(BaseModel):
    id: int
    product_id: int
    quantity: int
    price_at_addition: float
    model_config = ConfigDict(from_attributes=True)

class CartResponse(BaseModel):
    id: int
    user_id: int
    status: str
    total_amount: float
    items: List[CartItemResponse] = []
    model_config = ConfigDict(from_attributes=True)

class BillResponse(BaseModel):
    cart_id: int
    subtotal: float
    tax_amount: float
    grand_total: float
    currency: str = "PKR"