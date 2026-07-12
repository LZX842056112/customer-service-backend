from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    nickname: Mapped[str] = mapped_column(String(100))
    level: Mapped[str] = mapped_column(String(32))
    mobile_masked: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime)

    orders: Mapped[list["Order"]] = relationship(back_populates="user")


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    stock_status: Mapped[str] = mapped_column(String(32))
    cover_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    attributes_json: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime)


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(32))
    status_desc: Mapped[str] = mapped_column(String(255))
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    created_at: Mapped[datetime] = mapped_column(DateTime)
    receiver_name: Mapped[str] = mapped_column(String(64))
    receiver_phone_masked: Mapped[str] = mapped_column(String(32))
    receiver_address: Mapped[str] = mapped_column(String(255))

    user: Mapped[User] = relationship(back_populates="orders")
    items: Mapped[list["OrderItem"]] = relationship(back_populates="order")
    logistics_records: Mapped[list["LogisticsRecord"]] = relationship(back_populates="order")
    refund_requests: Mapped[list["RefundRequest"]] = relationship(back_populates="order")
    shipping_urges: Mapped[list["ShippingUrgeRequest"]] = relationship(back_populates="order")


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    title_snapshot: Mapped[str] = mapped_column(String(255))
    quantity: Mapped[int]
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))

    order: Mapped[Order] = relationship(back_populates="items")
    product: Mapped[Product] = relationship()


class LogisticsRecord(Base):
    __tablename__ = "logistics_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    logistics_company: Mapped[str] = mapped_column(String(64))
    tracking_number: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32))
    status_desc: Mapped[str] = mapped_column(String(255))
    updated_at: Mapped[datetime] = mapped_column(DateTime)

    order: Mapped[Order] = relationship(back_populates="logistics_records")
    traces: Mapped[list["LogisticsTrace"]] = relationship(back_populates="record")


class LogisticsTrace(Base):
    __tablename__ = "logistics_traces"

    id: Mapped[int] = mapped_column(primary_key=True)
    logistics_record_id: Mapped[int] = mapped_column(ForeignKey("logistics_records.id"))
    trace_time: Mapped[datetime] = mapped_column(DateTime)
    trace_desc: Mapped[str] = mapped_column(String(255))

    record: Mapped[LogisticsRecord] = relationship(back_populates="traces")


class RefundRequest(Base):
    __tablename__ = "refund_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    refund_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    operator: Mapped[str] = mapped_column(String(64))
    reason: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32))
    status_desc: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime)

    order: Mapped[Order] = relationship(back_populates="refund_requests")


class ShippingUrgeRequest(Base):
    __tablename__ = "shipping_urge_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    urge_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    operator: Mapped[str] = mapped_column(String(64))
    reason: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32))
    status_desc: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime)

    order: Mapped[Order] = relationship(back_populates="shipping_urges")
