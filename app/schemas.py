from datetime import datetime
from typing import List, Optional, Generic, TypeVar, Any
from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class DataResponse(BaseModel, Generic[T]):
    data: T


class UserOut(BaseModel):
    id: int
    email: str
    role: str
    active: bool

    model_config = ConfigDict(from_attributes=True)


class ProductCreate(BaseModel):
    sku: str
    name: str
    price_paise: int
    stock: int
    active: bool = True


class ProductUpdate(BaseModel):
    sku: Optional[str] = None
    name: Optional[str] = None
    price_paise: Optional[int] = None
    stock: Optional[int] = None
    active: Optional[bool] = None


class ProductOut(BaseModel):
    id: int
    sku: str
    name: str
    price_paise: int
    stock: int
    active: bool

    model_config = ConfigDict(from_attributes=True)


class CartItemAdd(BaseModel):
    product_id: int
    quantity: int


class CartItemOut(BaseModel):
    id: int
    product_id: int
    product_sku: str
    product_name: str
    price_paise: int
    quantity: int
    item_total_paise: int


class CartSnapshotOut(BaseModel):
    items: List[CartItemOut]
    total_paise: int


class CouponValidateIn(BaseModel):
    code: str
    subtotal_paise: int


class CouponValidateOut(BaseModel):
    valid: bool
    discount_paise: int


class CouponCreate(BaseModel):
    code: str
    percent_off: int
    expires_at: datetime
    active: bool = True


class CouponOut(BaseModel):
    id: int
    code: str
    percent_off: int
    expires_at: datetime
    active: bool

    model_config = ConfigDict(from_attributes=True)


class OrderCheckoutIn(BaseModel):
    coupon_code: Optional[str] = None


class OrderItemOut(BaseModel):
    id: int
    product_id: int
    product_sku: str
    product_name: str
    quantity: int
    unit_price_paise: int


class OrderOut(BaseModel):
    id: int
    user_id: int
    status: str
    subtotal_paise: int
    discount_paise: int
    total_paise: int
    coupon_id: Optional[int] = None
    created_at: datetime
    items: List[OrderItemOut] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class PaymentConfirmIn(BaseModel):
    order_id: int
    idempotency_key: str


class PaymentRefundIn(BaseModel):
    order_id: int


class PaymentOut(BaseModel):
    id: int
    order_id: int
    idempotency_key: str
    amount_paise: int
    status: str
    confirmed_at: datetime
    refunded_paise: int

    model_config = ConfigDict(from_attributes=True)


class LoginIn(BaseModel):
    email: str
    password: str
