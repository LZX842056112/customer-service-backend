from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class ApiResponse(BaseModel):
    code: int = 0
    message: str = "ok"
    data: Any


class OrderSummaryData(BaseModel):
    order_id: str
    title: str
    status: str
    amount: Decimal
    created_at: datetime
    cover_url: str | None = None


class ProductSummaryData(BaseModel):
    product_id: str
    title: str
    price: Decimal
    cover_url: str | None = None


class UserOrdersData(BaseModel):
    user_id: str
    orders: list[OrderSummaryData]


class UserProductsData(BaseModel):
    user_id: str
    products: list[ProductSummaryData]


class OrderItemData(BaseModel):
    product_id: str
    title: str
    quantity: int
    price: Decimal


class OrderDetailData(BaseModel):
    order_id: str
    status: str
    status_desc: str
    amount: Decimal
    created_at: datetime
    receiver_name: str
    receiver_phone_masked: str
    receiver_address: str
    items: list[OrderItemData]


class OrderStatusData(BaseModel):
    order_id: str
    status: str
    status_desc: str


class LogisticsTraceData(BaseModel):
    time: datetime
    desc: str


class LogisticsData(BaseModel):
    order_id: str
    logistics_company: str
    tracking_number: str
    status: str
    status_desc: str
    traces: list[LogisticsTraceData]


class ProductData(BaseModel):
    product_id: str
    title: str
    description: str
    price: Decimal
    stock_status: str
    cover_url: str | None = None
    attributes: dict[str, Any]


class UrgeShippingRequest(BaseModel):
    submitted_by: str = Field(default="system")
    note: str = Field(default="用户希望尽快发货")


class RefundRequestBody(BaseModel):
    submitted_by: str = Field(default="system")
    reason: str


class OperationResultData(BaseModel):
    request_type: str
    request_id: str
    order_id: str
    status: str
    status_desc: str
