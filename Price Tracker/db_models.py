from sqlalchemy.orm import relationship
from database import Base
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Boolean
from datetime import datetime, timezone

class User(Base): # to store user info
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    h_pass = Column(String, nullable=False) # hashed password
    products = relationship("Product", back_populates="owner", cascade="all, delete-orphan")

class Product(Base): # to view and put product details under user
    __tablename__ = "products"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"))
    search_q = Column(String, nullable=False) #lets you rerun the same search periodically in Celery(Experimental)
    data_id = Column(String, nullable=True)
    url = Column(String, nullable=True)
    img_url = Column(String, nullable=True)
    owner = relationship("User", back_populates="products")
    prices = relationship("PriceHistory", back_populates="product", cascade="all, delete-orphan")
    created_at = Column(DateTime, default= lambda: datetime.now(timezone.utc)) #helps in sorting
    alerts= relationship("Alert", back_populates="product", cascade="all, delete-orphan") #to clean unused child products

class PriceHistory(Base): # to track product for user
    __tablename__ = "price_history"
    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    price = Column(Integer, nullable=False)
    mrp = Column(Integer, nullable=True)
    scraped_at = Column(DateTime, default= lambda: datetime.now(timezone.utc))
    product = relationship("Product", back_populates="prices")

class Alert(Base): # alert to email
    __tablename__ = "alerts"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    threshold = Column(Integer, nullable=True, default=0) # just to avoid spam emails
    last_price_notify = Column(Integer, nullable=True)
    created_at = Column(DateTime, default= lambda: datetime.now(timezone.utc))
    product = relationship("Product", back_populates="alerts")
    is_active = Column(Boolean, default=True)

# class Platform(Base):
#     pass # for future options choosing between amazon or flipkart or other platforms