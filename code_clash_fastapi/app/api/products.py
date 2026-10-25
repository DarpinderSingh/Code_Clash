from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.services import product_service
from app.schemas import ProductOut, DataResponse
from typing import List

router = APIRouter(prefix="/api/products", tags=["products"])


@router.get("", response_model=DataResponse[List[ProductOut]])
def list_products_endpoint(db: Session = Depends(get_db)):
    products = product_service.list_products(db)
    return {"data": products}
