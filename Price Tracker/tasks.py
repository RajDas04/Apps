from celery import Celery
from config import settings
from database import SessionLocal
import db_models
from scraper import Scraper
from datetime import datetime, timezone
from notify import send_email
from celery.schedules import crontab

celery = Celery("price_tracker",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["tasks"])

celery.conf.update(accept_content=["json"],
                   beat_schedule={"scrape-all-on-2am":{
                                  "task": "scrape_all_products",
                                  "schedule": crontab(hour=2, minute=0)}}) # serializer is default json & timezone defalut utc

@celery.task(name="alert_system")
def alert_system(product_id: int, current_price: int):
    db = SessionLocal()
    try:
        product = db.query(db_models.Product).filter(db_models.Product.id == product_id).first()
        if not product:
            return {"error": "Product not found"}
        price_history = db.query(db_models.PriceHistory)\
            .filter(db_models.PriceHistory.product_id == product_id)\
            .order_by(db_models.PriceHistory.scraped_at.desc())\
            .limit(2)\
            .all()
        
        if len(price_history) < 2:
            return {"status": "insufficient_data"}
        
        alerts = db.query(db_models.Alert).filter(db_models.Alert.product_id == product_id,
                                                  db_models.Alert.is_active == True).all()
        
        previous_price = price_history[1].price
        price_drop = previous_price - current_price        
        if price_drop <= 0:
            for alert in alerts: # reset tracking price
                if alert.last_price_notify:
                    alert.last_price_notify = None
                    db.commit()
            return {"status": "no_drop"}
        
        for alert in alerts:
            if price_drop < alert.threshold: # checks
                continue
            if alert.last_price_notify and current_price >= alert.last_price_notify:
                continue
            
            user = db.query(db_models.User).filter(db_models.User.id == alert.user_id).first()
            if user:
                try:
                    send_email(to_email=user.email, product_name=product.name, current_price=current_price,
                               previous_price=previous_price, drop_amount=price_drop)
                    alert.last_price_notify = current_price # update tracking to new price
                    db.commit()
                except Exception as e:
                    print(f"Failed to send email to {user.email}: {e}")
                    db.rollback()
        return {"status": "checked and sended"}
        
    except Exception as e:
        print(f"Alert system error: {e}")
        db.rollback()
        raise
    finally:
        db.close()

@celery.task(name="scrape_prod", bind=True, max_retries=3)
def scrape_prod(self, product_id: int):
    scraper = Scraper(settings.scrape_url)
    db = SessionLocal()
    try:
        prod = db.query(db_models.Product).filter(db_models.Product.id==product_id).first()
        if not prod:
            return {"error": f"Product {product_id} not found"}
        current = None
        if prod.url:
            print(f"using url search for {prod.name}") # for debug
            current = scraper.search_and_extract_prices_by_url(prod.url)

        if not current:
            print(f"back to name search for {prod.name}") # for debug
            result = scraper.search_products(prod.search_q)
            current = next((r for r in result if r["data_id"] == prod.data_id), None)
            if not current: # potential edge case if exact product not found, widen the search
                narow_q = " ".join(prod.search_q.split()[:3]) # remove some words from behind
                result = scraper.search_products(narow_q)
                current = next((r for r in result if r["data_id"] == prod.data_id), None)
            if current and current.get("url"):
                prod.url = current["url"]
                print(f"saving this url for future use: {current['url']}")
                prod.img_url = current.get("image_url") # save image url
                db.commit()
        if not current:
            return {"error": f"Product data id {prod.data_id} for {prod.name} not found in results"}
        
        record = db_models.PriceHistory(
            product_id= prod.id,
            price= current["price"],
            mrp= current["mrp"],
            scraped_at= datetime.now(timezone.utc))
        db.add(record)
        db.commit()

        alert_system.delay(product_id, current["price"])  # chain to next task
        return {"product": prod.name, "price": current["price"]}

    except Exception as exc:
        db.rollback()
        raise self.retry(exc=exc, countdown=60)  # retry after 60 secs
    finally:
        db.close()
        
@celery.task(name="scrape_all_products")
def scrape_all_products():
    db = SessionLocal()
    try:
        products = db.query(db_models.Product).all()
        for product in products:
            scrape_prod.delay(product.id)
        return {"dispatched": len(products)}
    finally:
        db.close()