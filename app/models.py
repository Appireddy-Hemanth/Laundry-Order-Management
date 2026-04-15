from datetime import date, datetime, timedelta
from enum import Enum
from typing import Dict, List
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


PRICE_LIST: Dict[str, int] = {
    "shirt": 10,
    "pants": 15,
    "saree": 20,
}


class OrderStatus(str, Enum):
    RECEIVED = "RECEIVED"
    PROCESSING = "PROCESSING"
    READY = "READY"
    DELIVERED = "DELIVERED"


VALID_STATUS_TRANSITIONS = {
    OrderStatus.RECEIVED: {OrderStatus.PROCESSING},
    OrderStatus.PROCESSING: {OrderStatus.READY},
    OrderStatus.READY: {OrderStatus.DELIVERED},
    OrderStatus.DELIVERED: set(),
}


def can_transition_status(current: OrderStatus, target: OrderStatus) -> bool:
    if current == target:
        return True
    return target in VALID_STATUS_TRANSITIONS[current]


class GarmentInput(BaseModel):
    type: str = Field(..., description="Garment type")
    quantity: int = Field(..., gt=0, description="Number of items")

    @field_validator("type")
    @classmethod
    def validate_type(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in PRICE_LIST:
            allowed = ", ".join(PRICE_LIST.keys())
            raise ValueError(f"Invalid garment type '{value}'. Allowed: {allowed}")
        return normalized


class CreateOrderRequest(BaseModel):
    customer_name: str = Field(..., min_length=1)
    phone_number: str = Field(..., min_length=7, max_length=20)
    garments: List[GarmentInput] = Field(..., min_length=1)

    @field_validator("customer_name")
    @classmethod
    def validate_customer_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("customer_name cannot be empty")
        return cleaned

    @field_validator("phone_number")
    @classmethod
    def validate_phone_number(cls, value: str) -> str:
        cleaned = value.strip()
        allowed = set("+0123456789 -")
        if not cleaned or any(ch not in allowed for ch in cleaned):
            raise ValueError("phone_number can contain only digits, spaces, '+', and '-' characters")
        return cleaned


class GarmentLine(BaseModel):
    type: str
    quantity: int
    unit_price: int
    line_total: int


class Order(BaseModel):
    order_id: str
    customer_name: str
    phone_number: str
    garments: List[GarmentLine]
    total_bill: int
    status: OrderStatus
    estimated_delivery_date: date


class UpdateOrderStatusRequest(BaseModel):
    status: OrderStatus


class DashboardResponse(BaseModel):
    total_orders: int
    total_revenue: int
    orders_per_status: Dict[OrderStatus, int]


class StatusHistoryEntry(BaseModel):
    order_id: str
    previous_status: str
    new_status: OrderStatus
    changed_at: datetime


class GarmentAnalyticsItem(BaseModel):
    garment_type: str
    total_quantity: int
    total_revenue: int


def build_order_payload(payload: CreateOrderRequest) -> Order:
    garment_lines: List[GarmentLine] = []

    for item in payload.garments:
        unit_price = PRICE_LIST[item.type]
        line_total = unit_price * item.quantity
        garment_lines.append(
            GarmentLine(
                type=item.type,
                quantity=item.quantity,
                unit_price=unit_price,
                line_total=line_total,
            )
        )

    total = sum(item.line_total for item in garment_lines)

    return Order(
        order_id=str(uuid4()),
        customer_name=payload.customer_name,
        phone_number=payload.phone_number,
        garments=garment_lines,
        total_bill=total,
        status=OrderStatus.RECEIVED,
        estimated_delivery_date=date.today() + timedelta(days=2),
    )
