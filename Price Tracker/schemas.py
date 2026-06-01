from pydantic import BaseModel, EmailStr 

class Token(BaseModel):
    access_token: str
    token_type: str
    refresh_token: str

class TokenData(BaseModel):
    email: str | None= None

class RefreshRequest(BaseModel):
    refresh_token: str

class UserCreate(BaseModel):
    email: EmailStr
    password: str

class OTPverify(BaseModel):
    email: str
    otp: str

class UserOut(BaseModel):
    id: int
    email: str

    class Config:
        from_attributes = True

class ProductCreate(BaseModel):
    name: str
    data_id: str

class ProductOut(BaseModel):
    id: int
    name: str
    search_q: str

    class Config:
        from_attributes = True

# class AlertCreate(BaseModel):
#     product_id: int
#     threshold: int
 
# class AlertOut(BaseModel):
#     id: int
#     threshold: int
#     is_active: bool
 
#     class Config:
#         from_attributes = True