from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database.session import Base

class AuditMixin:
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    is_deleted = Column(Boolean, default=False, nullable=False)
    version = Column(Integer, default=1, nullable=False)

class User(Base, AuditMixin):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    name = Column(String(255))
    carts = relationship("Cart", back_populates="user")

class Product(Base, AuditMixin):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), index=True, nullable=False)
    price = Column(Float, nullable=False)
    stock = Column(Integer, default=0, nullable=False)
    reserved_stock = Column(Integer, default=0, nullable=False)

class Cart(Base, AuditMixin):
    __tablename__ = "carts"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(String(50), default="active", nullable=False)
    total_amount = Column(Float, default=0.0)
    user = relationship("User", back_populates="carts")
    items = relationship("CartItem", back_populates="cart")

class CartItem(Base, AuditMixin):
    __tablename__ = "cart_items"
    id = Column(Integer, primary_key=True, index=True)
    cart_id = Column(Integer, ForeignKey("carts.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity = Column(Integer, default=1, nullable=False)
    price_at_addition = Column(Float, nullable=False)
    cart = relationship("Cart", back_populates="items")