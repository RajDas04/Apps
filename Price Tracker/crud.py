from database import DBSession
import schemas
from auth import hasher
from db_models import User, Product, Alert
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from starlette import status

def create_user(db: DBSession, create_user_req: schemas.UserCreate):
    create_user_model = User(email=create_user_req.email,
                             h_pass= hasher.hash(create_user_req.password))
    db.add(create_user_model)
    try:
        db.commit()
        db.refresh(create_user_model)
        return create_user_model
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Something went Wrong")

def create_product(db: DBSession, product: schemas.ProductCreate, user_id: int):
    db_product = Product(name=product.name,
                         search_q=product.name,
                         user_id=user_id,
                         data_id= product.data_id)
    db.add(db_product)
    try:
        db.commit()
        db.refresh(db_product)

        alert_auto = Alert(user_id=user_id,
                           product_id=db_product.id,
                           threshold=0,
                           is_active=True)
        db.add(alert_auto)
        db.commit()
        db.refresh(alert_auto)

        return db_product
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Product already registered.")

def get_user_email(db: DBSession, email: str):
    return db.query(User).filter(User.email == email).first()

def get_user_products(db: DBSession, user_id: int):
    return db.query(Product).filter(Product.user_id == user_id).all()

def delete_product(db: DBSession, product_id: int, user_id: int):
    db_product = db.query(Product).filter(
        Product.id == product_id,
        Product.user_id == user_id).first()
    if not db_product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    
    db.delete(db_product)
    db.commit()
    return None