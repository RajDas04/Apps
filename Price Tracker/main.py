from fastapi import FastAPI, HTTPException, APIRouter, Depends, Request, Response
from scraper import Scraper
from fastapi.responses import JSONResponse, RedirectResponse, HTMLResponse
from database import engine, DBSession
import db_models, schemas, crud
from config import settings
from auth import userSession, optionaluserSession, login_for_access_token, refresh_token, login_for_access_cookie, refresh_cookie, verify_otp, create_and_store_otp, delete_otp
from starlette import status
from fastapi.security import OAuth2PasswordRequestForm
from tasks import scrape_all_products, scrape_prod
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter
from slowapi.util import get_remote_address
from notify import send_otp
# import csv, os

# region Variables
app = FastAPI()
router = APIRouter(prefix="/auth", tags=["auth"])
scraper = Scraper(settings.scrape_url)
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")
limiter = Limiter(key_func=get_remote_address)

# db_models.Base.metadata.drop_all(bind=engine) # use this only in dev during publish delete it
db_models.Base.metadata.create_all(bind=engine)

@app.get("/")
def root(request: Request, current_user: optionaluserSession):
    return templates.TemplateResponse("search.html", {"request": request,
                                                        "user": current_user.get("username") if current_user else None})

# @app.get("/result") ####
# def result():
#     row = []
#     try:
#         with open("output.csv", mode="r", newline='', encoding="utf-8") as f:
#             reader = csv.DictReader(f)
#             row = [r for r in reader]
#     except FileNotFoundError:
#         row = []
#     return row

# @app.get("/search_csv")  ####
# def search(q:str):  # ?q=yourproduct
#     products = scraper.search_products(q)
#     fieldnames = ["product", "price", "mrp", "updated_on"]
#     file_exists = os.path.isfile("output.csv") and os.path.getsize("output.csv") > 0
    
#     with open("output.csv", mode="a", newline='', encoding="utf-8") as f:
#         writer = csv.DictWriter(f, fieldnames=fieldnames)
#         if not file_exists:
#             writer.writeheader()
#         writer.writerows(products)
    
#     return JSONResponse(content=products)

# @app.get("/manual")
# def manual_db_scrape(q:str, db: DBSession, current_user: userSession):  # /manual?q=yourproduct
#     products = scraper.search_products(q)
#     if not products:
#         return JSONResponse(status_code=404, content={"Error Detail": "No product found"})
    
#     scraped = []
#     for p in products:
#         product = db_models.Product(
#             name = p["product"],
#             search_q = q,
#             user_id = current_user["id"]
#         )
#         db.add(product)
#         db.flush()
        
#         record = db_models.PriceHistory(
#             product_id = product.id,
#             price = p["price"],
#             mrp = p["mrp"]
#         )
#         db.add(record)
#         scraped.append({"product": p["product"], "price": p["price"], "mrp": p["mrp"]})
#     db.commit()
#     return JSONResponse(content={"scraped": len(scraped), "products": scraped})

# @app.get("/gotit", status_code=200)
# def user(user: userSession, db: DBSession):
#     if user is None:
#         raise HTTPException(status_code=401, detail="Authentication Failed")
#     return {"User": user}

# region Product CRUD
@app.post("/products", response_model=schemas.ProductOut, tags=["products"])
def add_product(product: schemas.ProductCreate, db: DBSession, current_user: userSession):
    return crud.create_product(db, product, current_user["id"])

@app.get("/products", response_model=list[schemas.ProductOut], tags=["products"])
def get_products(db: DBSession, current_user: userSession):
    return crud.get_user_products(db, current_user["id"])

@app.delete("/products/{product_id}", status_code=204)
def delete_product(product_id: int, db: DBSession, current_user: userSession, response: Response):
    response.headers["HX-Redirect"] = "/dashboard?deleted=1"
    return crud.delete_product(db, product_id, current_user["id"])

# region Search and Scrape
@app.post("/scrape/all", tags=["scraper"])
def trigger_all(user: userSession):
    task = scrape_all_products.delay()
    return {"task_id": task.id, "status": "queued"}

@app.post("/scrape/{product_id}", tags=["scraper"])
def trigger_scrape(product_id: int, user: userSession):
    task = scrape_prod.delay(product_id)
    return {"task_id": task.id, "status": "queued"}

@app.get("/search")
def search_page(request: Request, current_user: optionaluserSession):
    return templates.TemplateResponse("search.html", {"request": request,
                                                        "user": current_user["username"] if current_user else None})

@app.get("/api/search")
def api_search(q: str, request: Request, current_user: optionaluserSession):
    if not q.strip():
        return templates.TemplateResponse(
            "others/search_api.html",
            {"request": request, "products": []})

    products = scraper.search_products(q)
    return templates.TemplateResponse(
        "others/search_api.html",
        {
            "request": request,
            "products": products,
            "query": q,
            "user": current_user
        }
    ) # Returns search results as JSON for HTMX to render.

# region Login and Refresh
@app.get("/login")
def login_page(request: Request):
    return templates.TemplateResponse("authorization/login.html", {"request": request})

@router.post("/login/cookie", response_model=schemas.Token)
def login_cookie(response: Response, db: DBSession, form: OAuth2PasswordRequestForm = Depends()):
    log_detail = login_for_access_cookie(form, db, response)
    response.headers["HX-Redirect"] = "/dashboard"
    return log_detail

# @router.post("/login_docs", response_model=schemas.Token)
# def login(db: DBSession, form: OAuth2PasswordRequestForm = Depends()):
#     return login_for_access_token(form, db)

@router.post("/refresh/cookie", response_model=schemas.Token)
@limiter.limit("10/minute") # 10 per minute
def refresh(request: Request, response: Response):
    return refresh_cookie(request, response)

# region Register
@app.get("/signin")
def register_page(request: Request):
    return templates.TemplateResponse("authorization/register.html", {"request": request})

# @router.post("/signin", status_code=status.HTTP_201_CREATED, response_model=schemas.UserOut)
# def register(user: schemas.UserCreate, db: DBSession, response: Response): 
#     if crud.get_user_email(db, user.email):
#         raise HTTPException(status_code=400, detail="Email already registered")
#     response.headers["HX-Redirect"] = "/login"
#     return crud.create_user(db, user)

@router.post("/signin/request", status_code=202)
@limiter.limit("3/minute")
def register_otp(user: schemas.UserCreate, db: DBSession):
    if crud.get_user_email(db, user.email):
        raise HTTPException(status_code=400, detail="Email already registered")
    exists = verify_otp(user.email)
    if exists:
        raise HTTPException(status_code=400, detail="OTP already sent. Please check your email.")
    otp = create_and_store_otp(user.email, user.password)
    send_otp(user.email, otp)
    return {"message": "OTP sent to your email. Expires in 10 minutes."}

@router.post("/signin/verify", status_code=201, response_model=schemas.UserOut)
def register_verify(otp_req: schemas.OTPverify, response: Response, db: DBSession):
    pending = verify_otp(otp_req.email)
    if not pending:
        raise HTTPException(status_code=400, detail="OTP expired or not found. Please register again.")
    if pending["otp"] != otp_req.otp:
        raise HTTPException(status_code=400, detail="Invalid OTP")
    user = schemas.UserCreate(email=otp_req.email, password=pending["password"])
    created_user = crud.create_user(db, user)
    delete_otp(otp_req.email)
    response.headers["HX-Redirect"] = "/login"
    return created_user

# region Logout
@app.get("/logout")
def logout(response: Response, request: Request):
    referer = request.headers.get("referer", "") # on logout if user is in search stays or to login
    if "/search" in referer:
        response = RedirectResponse(url="/search", status_code=302)
    else:
        response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    return response

# @app.delete("/users/me", status_code=204)
# def delete_user(password: str, db: DBSession, current_user: userSession):
#     return crud.delete_user(db, current_user["id"], password) # password confirmtion

# region Dashboard
@app.get("/dashboard")
def user_dashboard(request: Request, db: DBSession, current_user: userSession):
    products = crud.get_user_products(db, current_user["id"])
    prod_with_price = []
    for p in products:
        recent = db.query(db_models.PriceHistory)\
            .filter(db_models.PriceHistory.product_id == p.id)\
            .order_by(db_models.PriceHistory.scraped_at)\
            .first()
        prod_with_price.append({"product": p, "latest": recent})
    return templates.TemplateResponse("user_dashboard/homepage.html", {
        "request": request,
        "products": prod_with_price,
        "user": current_user["username"]
    })

@app.get("/dashboard/{product_id}")
def product_detail(product_id: int, request: Request, db: DBSession, current_user: userSession):
    product = db.query(db_models.Product).filter(db_models.Product.id == product_id).first()
    prices = db.query(db_models.PriceHistory)\
        .filter(db_models.PriceHistory.product_id == product_id)\
        .order_by(db_models.PriceHistory.scraped_at)\
        .all()
    chart_data = {
        "labels": [p.scraped_at.strftime('%d %b %H:%M') for p in prices],
        "prices": [p.price for p in prices],
        "mrps": [p.mrp for p in prices]
    }
    return templates.TemplateResponse("user_dashboard/product.html", {
        "request": request,
        "product": product,
        "chart_data": chart_data,
        "prices": prices,
        "user": current_user["username"]
    })   

# @router.put("/alerts/{alert_id}", response_model=schemas.AlertOut)
# def edit_alert(alert_id: int, alert_req: schemas.AlertOut, db: DBSession, current_user: userSession):
#     return crud.update_alert_and_check(db, alert_id, alert_req, current_user.id)

app.include_router(router)
# from here