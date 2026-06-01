from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy import create_engine
from config import settings
from typing import Annotated
from fastapi import Depends
from sqlalchemy.orm import Session

engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class Base(DeclarativeBase):
    pass

DBSession = Annotated[Session, Depends(get_db)]