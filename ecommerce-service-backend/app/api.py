from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import (
    LogisticsRecord,
    Order,
    OrderItem,
    Product,
    RefundRequest,
    ShippingUrgeRequest,
    User,
)
from app.schemas import (
    ApiResponse,
    LogisticsData,
    LogisticsTraceData,
    OrderDetailData,
    OrderItemData,
    OrderSummaryData,
    OperationResultData,
    OrderStatusData,
    ProductData,
    ProductSummaryData,
    RefundRequestBody,
    UserOrdersData,
    UserProductsData,
    UrgeShippingRequest,
)


router = APIRouter()


def _wrap(data):
    return ApiResponse(data=data)


def _get_user_or_404(db: Session, user_id: str) -> User:
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"用户 {user_id} 不存在。")
    return user


def _build_recent_orders(db: Session, user: User, limit: int = 5) -> list[OrderSummaryData]:
    recent_orders = (
        db.query(Order)
        .options(joinedload(Order.items).joinedload(OrderItem.product))
        .filter(Order.user_id == user.id)
        .order_by(Order.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        OrderSummaryData(
            order_id=order.order_id,
            title=order.items[0].title_snapshot if order.items else "未知商品",
            status=order.status,
            amount=order.amount,
            created_at=order.created_at,
            cover_url=order.items[0].product.cover_url if order.items and order.items[0].product else None,
        )
        for order in recent_orders
    ]


def _build_recent_products(db: Session, user: User, limit: int = 5) -> list[ProductSummaryData]:
    recent_items = (
        db.query(OrderItem)
        .join(Order, Order.id == OrderItem.order_id)
        .join(Product, Product.id == OrderItem.product_id)
        .filter(Order.user_id == user.id)
        .options(joinedload(OrderItem.product))
        .order_by(Order.created_at.desc())
        .limit(limit)
        .all()
    )

    seen_product_ids: set[str] = set()
    products: list[ProductSummaryData] = []
    for item in recent_items:
        product = item.product
        if not product or product.product_id in seen_product_ids:
            continue
        seen_product_ids.add(product.product_id)
        products.append(
            ProductSummaryData(
                product_id=product.product_id,
                title=product.title,
                price=product.price,
                cover_url=product.cover_url,
            )
        )
    return products


def _get_order_or_404(db: Session, order_id: str) -> Order:
    order = (
        db.query(Order)
        .options(joinedload(Order.items).joinedload(OrderItem.product))
        .filter(Order.order_id == order_id)
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail=f"订单 {order_id} 不存在。")
    return order


def _get_product_or_404(db: Session, product_id: str) -> Product:
    product = db.query(Product).filter(Product.product_id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail=f"商品 {product_id} 不存在。")
    return product


@router.get(
    "/health",
    response_model=ApiResponse,
    tags=["系统"],
    summary="健康检查",
    description="用于检查服务和数据库连接是否正常。",
)
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return _wrap({"status": "ok"})


@router.get(
    "/users/{user_id}/orders",
    response_model=ApiResponse,
    tags=["用户"],
    summary="查询用户最近订单列表",
    description="根据用户 ID 查询最近订单，用于前端展示订单对象列表。",
)
def user_orders(user_id: str, db: Session = Depends(get_db)):
    user = _get_user_or_404(db, user_id)
    return _wrap(UserOrdersData(user_id=user.user_id, orders=_build_recent_orders(db, user)))


@router.get(
    "/users/{user_id}/products",
    response_model=ApiResponse,
    tags=["用户"],
    summary="查询用户最近商品列表",
    description="根据用户 ID 查询最近购买或关联过的商品，用于前端展示商品对象列表。",
)
def user_products(user_id: str, db: Session = Depends(get_db)):
    user = _get_user_or_404(db, user_id)
    return _wrap(UserProductsData(user_id=user.user_id, products=_build_recent_products(db, user)))


@router.get(
    "/orders/{order_id}",
    response_model=ApiResponse,
    tags=["订单"],
    summary="查询订单详情",
    description="根据订单 ID 查询订单主信息、收货信息以及订单商品明细。",
)
def order_detail(order_id: str, db: Session = Depends(get_db)):
    order = _get_order_or_404(db, order_id)
    return _wrap(
        OrderDetailData(
            order_id=order.order_id,
            status=order.status,
            status_desc=order.status_desc,
            amount=order.amount,
            created_at=order.created_at,
            receiver_name=order.receiver_name,
            receiver_phone_masked=order.receiver_phone_masked,
            receiver_address=order.receiver_address,
            items=[
                OrderItemData(
                    product_id=item.product.product_id if item.product else "",
                    title=item.title_snapshot,
                    quantity=item.quantity,
                    price=item.price,
                )
                for item in order.items
            ],
        )
    )


@router.get(
    "/orders/{order_id}/status",
    response_model=ApiResponse,
    tags=["订单"],
    summary="查询订单状态",
    description="返回订单当前状态及面向用户展示的状态说明。",
)
def order_status(order_id: str, db: Session = Depends(get_db)):
    order = _get_order_or_404(db, order_id)
    return _wrap(
        OrderStatusData(
            order_id=order.order_id,
            status=order.status,
            status_desc=order.status_desc,
        )
    )


@router.get(
    "/orders/{order_id}/logistics",
    response_model=ApiResponse,
    tags=["订单"],
    summary="查询订单物流信息",
    description="返回物流公司、运单号、当前物流状态和物流轨迹。",
)
def order_logistics(order_id: str, db: Session = Depends(get_db)):
    order = _get_order_or_404(db, order_id)
    record = (
        db.query(LogisticsRecord)
        .options(joinedload(LogisticsRecord.traces))
        .filter(LogisticsRecord.order_id == order.id)
        .order_by(LogisticsRecord.updated_at.desc())
        .first()
    )
    if not record:
        raise HTTPException(status_code=404, detail=f"订单 {order_id} 暂无物流信息。")

    traces = sorted(record.traces, key=lambda item: item.trace_time, reverse=True)
    return _wrap(
        LogisticsData(
            order_id=order.order_id,
            logistics_company=record.logistics_company,
            tracking_number=record.tracking_number,
            status=record.status,
            status_desc=record.status_desc,
            traces=[
                LogisticsTraceData(time=trace.trace_time, desc=trace.trace_desc)
                for trace in traces
            ],
        )
    )


@router.get(
    "/products/{product_id}",
    response_model=ApiResponse,
    tags=["商品"],
    summary="查询商品详情",
    description="根据商品 ID 查询商品标题、描述、价格、库存状态和规格参数。",
)
def product_detail(product_id: str, db: Session = Depends(get_db)):
    product = _get_product_or_404(db, product_id)
    return _wrap(
        ProductData(
            product_id=product.product_id,
            title=product.title,
            description=product.description,
            price=product.price,
            stock_status=product.stock_status,
            cover_url=product.cover_url,
            attributes=product.attributes_json or {},
        )
    )


@router.post(
    "/orders/{order_id}/shipping-reminders",
    response_model=ApiResponse,
    tags=["订单"],
    summary="创建发货提醒",
    description="为指定订单创建一条发货提醒请求。当前仅允许对待发货或待揽收订单发起提醒。",
)
def create_shipping_reminder(
    order_id: str,
    body: UrgeShippingRequest,
    db: Session = Depends(get_db),
):
    order = _get_order_or_404(db, order_id)
    if order.status not in {"待发货", "待揽收"}:
        raise HTTPException(
            status_code=400,
            detail=f"订单当前状态为“{order.status}”，当前不适合再次发起发货提醒。",
        )

    operation_id = f"U{datetime.now():%Y%m%d%H%M%S}{uuid4().hex[:6].upper()}"
    urge = ShippingUrgeRequest(
        urge_id=operation_id,
        order_id=order.id,
        operator=body.submitted_by,
        reason=body.note,
        status="submitted",
        status_desc="发货提醒已创建，商家会尽快处理。",
        created_at=datetime.now(),
    )
    db.add(urge)
    db.commit()

    return _wrap(
        OperationResultData(
            request_type="shipping_reminder",
            request_id=operation_id,
            order_id=order.order_id,
            status="submitted",
            status_desc=urge.status_desc,
        )
    )


@router.post(
    "/orders/{order_id}/refund-applications",
    response_model=ApiResponse,
    tags=["订单"],
    summary="创建退款申请",
    description="为指定订单创建退款申请。如果订单已有进行中的退款申请，将返回冲突错误。",
)
def create_refund_application(
    order_id: str,
    body: RefundRequestBody,
    db: Session = Depends(get_db),
):
    order = _get_order_or_404(db, order_id)

    existing = (
        db.query(RefundRequest)
        .filter(RefundRequest.order_id == order.id)
        .order_by(RefundRequest.created_at.desc())
        .first()
    )
    if existing and existing.status in {"submitted", "processing"}:
        raise HTTPException(
            status_code=409,
            detail=f"订单 {order_id} 已存在进行中的退款申请。",
        )

    operation_id = f"R{datetime.now():%Y%m%d%H%M%S}{uuid4().hex[:6].upper()}"
    refund = RefundRequest(
        refund_id=operation_id,
        order_id=order.id,
        operator=body.submitted_by,
        reason=body.reason,
        status="submitted",
        status_desc="退款申请已提交，正在审核中。",
        created_at=datetime.now(),
    )
    db.add(refund)
    db.commit()

    return _wrap(
        OperationResultData(
            request_type="refund_application",
            request_id=operation_id,
            order_id=order.order_id,
            status="submitted",
            status_desc=refund.status_desc,
        )
    )
