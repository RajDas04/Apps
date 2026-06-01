from database import DBSession
import schemas
from auth import hasher
from db_models import User, Product, Alert, PriceHistory
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from starlette import status
# from tasks import alert_system

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

# def get_user_alerts(db: DBSession, user_id: int):
#     return db.query(Alert).filter(Alert.user_id == user_id).all()

def delete_product(db: DBSession, product_id: int, user_id: int):
    db_product = db.query(Product).filter(
        Product.id == product_id,
        Product.user_id == user_id).first()
    if not db_product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    
    db.delete(db_product)
    db.commit()
    return None

# def create_alert(db: DBSession, alert: schemas.AlertCreate, user_id: int): # manual alert create
#     product = db.query(Product).filter(
#         Product.id == alert.product_id,
#         Product.user_id == user_id).first()
#     if not product:
#         raise HTTPException(
#             status_code=status.HTTP_404_NOT_FOUND, detail="Product not found or doesn't belong to you")
    
#     existing = db.query(Alert).filter(
#         Alert.product_id == alert.product_id,
#         Alert.user_id == user_id,
#         Alert.is_active == True
#     ).first()
#     if existing:
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST, detail="Active alert already exists for this product")
    
#     db_alert = Alert(
#         user_id=user_id,
#         product_id=alert.product_id,
#         threshold=alert.threshold
#     )
#     db.add(db_alert)
#     try:
#         db.commit()
#         db.refresh(db_alert)
#         return db_alert
#     except IntegrityError:
#         db.rollback()
#         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to create alert")
 
# def update_alert(db: DBSession, alert_id: int, alert_update: schemas.AlertOut, user_id: int):
#     db_alert = db.query(Alert).filter(
#         Alert.id == alert_id,
#         Alert.user_id == user_id).first()

#     if not db_alert:
#         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")

#     if alert_update.threshold is not None:
#         db_alert.threshold = alert_update.threshold
#         db_alert.is_active = True  # reactivate when threshold changes

#     if alert_update.is_active is not None:
#         db_alert.is_active = alert_update.is_active
#     try:
#         db.commit()
#         db.refresh(db_alert)
#         return db_alert
#     except IntegrityError:
#         db.rollback()
#         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to update alert")
    
# def update_alert_and_check(db: DBSession, alert_id: int, alert_update: schemas.AlertOut, user_id: int):
#     db_alert = update_alert(db, alert_id, alert_update, user_id)

#     latest_price = db.query(PriceHistory).filter(
#         PriceHistory.product_id == db_alert.product_id).order_by(PriceHistory.scraped_at.desc()).first()
#     if latest_price:
#         alert_system.delay(db_alert.product_id, latest_price.price)

#     return db_alert

# def delete_user(db: DBSession, user_id: int, password: str):
#     db_user = db.query(User).filter(User.id == user_id).first()

#     if not db_user:
#         raise HTTPException(status_code=404, detail="user not found")
#     if not hasher.verify(password, db_user.h_pass):
#         raise HTTPException(status_code=401, detail="invalid password")
    
#     db.delete(db_user)
#     db.commit()