from jose import jwt, JWTError
from config import settings
from datetime import datetime, timedelta, timezone
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi import Depends, HTTPException, Request, Response
from database import DBSession
from starlette import status
from db_models import User
from pwdlib import PasswordHash
from typing import Annotated, Optional
import random, redis, json

SECRET_KEY = settings.secret_key
ALGORITHM = settings.algorithm
ACCESS_TOKEN_EXPIRE_MINUTES = settings.access_token_expire_minutes
REFRESH_TOKEN_EXPIRE_DAYS = settings.refresh_token_expire_days

Oauth2_bear = OAuth2PasswordBearer(tokenUrl= "auth/login")
hasher = PasswordHash.recommended()
creds_exception = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                detail="Could not validate credentials")
redis_cli = redis.from_url(settings.redis_url)

def authenticate_user(email: str, password: str, db: DBSession):
    user = db.query(User).filter(User.email == email).first()
    if not user:
        return False
    if not hasher.verify(password, user.h_pass):
        return False
    return user

def create_token(email: str, user_id: int, expiration: timedelta):
    encode = {'sub': email, 'id': user_id}
    expires = datetime.now(timezone.utc) + expiration
    encode.update({'exp': expires})
    return jwt.encode(encode, SECRET_KEY, algorithm=ALGORITHM)

def create_refresh_token(email: str, user_id: int):
    encode = {'sub': email, 'id': user_id, 'type': 'refresh'}
    expires = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    encode.update({'exp': expires})
    return jwt.encode(encode, SECRET_KEY, algorithm=ALGORITHM)

def refresh_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "refresh":
            raise creds_exception
        email = payload.get("sub")
        user_id = payload.get("id")
        if email is None or user_id is None:
            raise creds_exception
        new_token = create_token(email, user_id, timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
        new_refresh_token = create_refresh_token(email, user_id)
        return {"access_token": new_token, "refresh_token": new_refresh_token,"token_type": "bearer"}
    except JWTError:
        raise creds_exception

def get_current_user(request: Request):
    token = request.cookies.get("access_token") # cookie 
    if not token:
        auth_head = request.headers.get("authorization")
        if auth_head and auth_head.lower().startswith("bearer "):
            token = auth_head.split(" ",1)[1]
    if not token:
        raise creds_exception
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        user_id: int = payload.get("id")
        if email is None or user_id is None:
            raise creds_exception
        if payload.get("type") == "refresh": # to check if refresh token is not being refreshed
            raise creds_exception
        return {'username': email, 'id': user_id}
    except JWTError:
        raise creds_exception

def get_current_user_optional(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        auth_head = request.headers.get("authorization")
        if auth_head and auth_head.lower().startswith("bearer "):
            token = auth_head.split(" ", 1)[1]
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        user_id: int = payload.get("id")
        if email is None or user_id is None:
            return None
        if payload.get("type") == "refresh":
            return None
        return {'username': email, 'id': user_id}
    except JWTError:
        return None
    
def login_for_access_token(form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
                           db: DBSession):
    user = authenticate_user(form_data.username, form_data.password, db)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User email or password is not valid.")
    token = create_token(user.email, user.id, timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    new_token = create_refresh_token(user.email, user.id)
    return{"access_token": token, "refresh_token": new_token, "token_type": "bearer"}

userSession = Annotated[dict, Depends(get_current_user)]
optionaluserSession = Annotated[Optional[dict], Depends(get_current_user_optional)]

def login_for_access_cookie(form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
                           db: DBSession, response: Response):
    user = authenticate_user(form_data.username, form_data.password, db)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User email or password is not valid.")
    token = create_token(user.email, user.id, timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    new_token = create_refresh_token(user.email, user.id)

    response.set_cookie(key="access_token",
                        value=token,
                        httponly=True,
                        samesite="lax",
                        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
                        secure=True,
                        path="/")
    response.set_cookie(key="refresh_token",
                        value=new_token,
                        httponly=True,
                        samesite="lax",
                        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
                        secure=True,
                        path="/")
    return{"access_token": token, "refresh_token": new_token, "token_type": "bearer"}

def refresh_cookie(request: Request, response: Response):
    token = request.cookies.get("refresh_token")
    if not token:
        raise creds_exception
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "refresh":
            raise creds_exception
        email = payload.get("sub")
        user_id = payload.get("id")

        if email is None or user_id is None:
            raise creds_exception
        new_access_token = create_token(email, user_id,
                                        timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
        new_refresh_token = create_refresh_token(email, user_id)

        response.set_cookie(key="access_token",
                            value=new_access_token,
                            httponly=True,
                            samesite="lax",
                            max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
                            path="/",)
        response.set_cookie(key="refresh_token",
                            value=new_refresh_token,
                            httponly=True,
                            samesite="lax",
                            max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
                            path="/",)
        return {"access_token": new_access_token, "refresh_token": new_refresh_token,
                "token_type": "bearer"}
    except JWTError:
        raise creds_exception

def create_and_store_otp(email: str, password:str):
    otp = ""
    for _ in range(6):
        otp += str(random.randint(0, 9))
    data = json.dumps({"email": email,
                       "password": password,
                       "otp": otp})
    redis_cli.setex(email, 600, data)
    return otp

def verify_otp(email: str):
    stored = redis_cli.get(email)
    if not stored:
        return False
    return json.loads(stored)

def delete_otp(email: str):
    redis_cli.delete(email)