from datetime import date
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from app.models import (
    CreateOrderRequest,
    DashboardResponse,
    GarmentAnalyticsItem,
    Order,
    OrderStatus,
    StatusHistoryEntry,
    UpdateOrderStatusRequest,
    build_order_payload,
    can_transition_status,
)
from app.storage import (
    add_status_history,
    delete_order,
    get_all_orders,
    get_order,
    get_status_history,
    save_order,
)

router = APIRouter(tags=["Laundry Orders"])


@router.post("/orders", response_model=Order, status_code=201)
def create_order(payload: CreateOrderRequest) -> Order:
    order = build_order_payload(payload)
    save_order(order)
    add_status_history(order.order_id, "CREATED", order.status)
    return order


@router.patch("/orders/{order_id}/status", response_model=Order)
def update_order_status(order_id: str, payload: UpdateOrderStatusRequest) -> Order:
    order = get_order(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Invalid order_id. Order not found.")

    if not can_transition_status(order.status, payload.status):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid status transition: {order.status.value} -> {payload.status.value}. "
                "Allowed flow: RECEIVED -> PROCESSING -> READY -> DELIVERED"
            ),
        )

    previous_status = order.status
    order.status = payload.status
    save_order(order)
    add_status_history(order_id, previous_status=previous_status.value, new_status=payload.status)
    return order


@router.get("/orders/{order_id}", response_model=Order)
def get_order_by_id(order_id: str) -> Order:
    order = get_order(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Invalid order_id. Order not found.")
    return order


@router.get("/orders", response_model=List[Order])
def list_orders(
    status: Optional[OrderStatus] = Query(None),
    customer_name: Optional[str] = Query(None),
    phone_number: Optional[str] = Query(None),
    garment_type: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
) -> List[Order]:
    orders = get_all_orders()

    if status is not None:
        orders = [order for order in orders if order.status == status]

    if customer_name:
        name_filter = customer_name.strip().lower()
        orders = [order for order in orders if name_filter in order.customer_name.lower()]

    if phone_number:
        phone_filter = phone_number.strip()
        orders = [order for order in orders if phone_filter in order.phone_number]

    if garment_type:
        garment_filter = garment_type.strip().lower()
        orders = [
            order
            for order in orders
            if any(item.type == garment_filter for item in order.garments)
        ]

    return orders[skip : skip + limit]


@router.delete("/orders/{order_id}")
def remove_order(order_id: str) -> dict:
    deleted = delete_order(order_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Invalid order_id. Order not found.")
    return {"message": "Order deleted successfully", "order_id": order_id}


@router.get("/orders/{order_id}/history", response_model=List[StatusHistoryEntry])
def order_status_history(order_id: str) -> List[StatusHistoryEntry]:
    order = get_order(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Invalid order_id. Order not found.")
    return get_status_history(order_id)


@router.get("/dashboard", response_model=DashboardResponse)
def get_dashboard() -> DashboardResponse:
    orders = get_all_orders()

    count_by_status = {status: 0 for status in OrderStatus}
    for order in orders:
        count_by_status[order.status] += 1

    return DashboardResponse(
        total_orders=len(orders),
        total_revenue=sum(order.total_bill for order in orders),
        orders_per_status=count_by_status,
    )


@router.get("/reports/delayed", response_model=List[Order])
def delayed_orders() -> List[Order]:
    today = date.today()
    return [
        order
        for order in get_all_orders()
        if order.status != OrderStatus.DELIVERED and order.estimated_delivery_date < today
    ]


@router.get("/reports/garments", response_model=List[GarmentAnalyticsItem])
def garment_analytics() -> List[GarmentAnalyticsItem]:
    aggregate: Dict[str, Dict[str, int]] = {}
    for order in get_all_orders():
        for item in order.garments:
            if item.type not in aggregate:
                aggregate[item.type] = {"quantity": 0, "revenue": 0}
            aggregate[item.type]["quantity"] += item.quantity
            aggregate[item.type]["revenue"] += item.line_total

    return [
        GarmentAnalyticsItem(
            garment_type=garment_type,
            total_quantity=values["quantity"],
            total_revenue=values["revenue"],
        )
        for garment_type, values in sorted(aggregate.items())
    ]
