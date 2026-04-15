import json
import os
from datetime import UTC, date, datetime
from typing import Dict, List, Optional

from sqlalchemy import Column, Date, DateTime, Integer, String, Text, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.models import GarmentLine, Order, OrderStatus, StatusHistoryEntry

# In-memory store for orders.
ORDERS: Dict[str, Order] = {}
ORDER_STATUS_HISTORY: Dict[str, List[StatusHistoryEntry]] = {}

DATABASE_URL = "sqlite:///./laundry.db"
Base = declarative_base()
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class OrderDB(Base):
	__tablename__ = "orders"

	order_id = Column(String, primary_key=True, index=True)
	customer_name = Column(String, nullable=False)
	phone_number = Column(String, nullable=False)
	garments_json = Column(Text, nullable=False)
	total_bill = Column(Integer, nullable=False)
	status = Column(String, nullable=False)
	estimated_delivery_date = Column(Date, nullable=False)


class OrderStatusHistoryDB(Base):
	__tablename__ = "order_status_history"

	id = Column(Integer, primary_key=True, index=True)
	order_id = Column(String, nullable=False, index=True)
	previous_status = Column(String, nullable=False)
	new_status = Column(String, nullable=False)
	changed_at = Column(DateTime, nullable=False, index=True)


def _backend() -> str:
	return os.getenv("STORAGE_BACKEND", "memory").strip().lower()


def _to_db(order: Order) -> OrderDB:
	return OrderDB(
		order_id=order.order_id,
		customer_name=order.customer_name,
		phone_number=order.phone_number,
		garments_json=json.dumps([item.model_dump() for item in order.garments]),
		total_bill=order.total_bill,
		status=order.status.value,
		estimated_delivery_date=order.estimated_delivery_date,
	)


def _to_model(row: OrderDB) -> Order:
	garments = [GarmentLine(**item) for item in json.loads(row.garments_json)]
	return Order(
		order_id=row.order_id,
		customer_name=row.customer_name,
		phone_number=row.phone_number,
		garments=garments,
		total_bill=row.total_bill,
		status=OrderStatus(row.status),
		estimated_delivery_date=date.fromisoformat(str(row.estimated_delivery_date)),
	)


def init_storage() -> None:
	if _backend() == "sqlite":
		Base.metadata.create_all(bind=engine)


def save_order(order: Order) -> None:
	if _backend() == "sqlite":
		db = SessionLocal()
		try:
			existing = db.query(OrderDB).filter(OrderDB.order_id == order.order_id).first()
			if existing is None:
				db.add(_to_db(order))
			else:
				existing.customer_name = order.customer_name
				existing.phone_number = order.phone_number
				existing.garments_json = json.dumps([item.model_dump() for item in order.garments])
				existing.total_bill = order.total_bill
				existing.status = order.status.value
				existing.estimated_delivery_date = order.estimated_delivery_date
			db.commit()
		finally:
			db.close()
		return

	ORDERS[order.order_id] = order


def get_order(order_id: str) -> Optional[Order]:
	if _backend() == "sqlite":
		db = SessionLocal()
		try:
			row = db.query(OrderDB).filter(OrderDB.order_id == order_id).first()
			return _to_model(row) if row else None
		finally:
			db.close()

	return ORDERS.get(order_id)


def get_all_orders() -> List[Order]:
	if _backend() == "sqlite":
		db = SessionLocal()
		try:
			rows = db.query(OrderDB).all()
			return [_to_model(row) for row in rows]
		finally:
			db.close()

	return list(ORDERS.values())


def delete_order(order_id: str) -> bool:
	if _backend() == "sqlite":
		db = SessionLocal()
		try:
			row = db.query(OrderDB).filter(OrderDB.order_id == order_id).first()
			if row is None:
				return False
			db.query(OrderStatusHistoryDB).filter(OrderStatusHistoryDB.order_id == order_id).delete()
			db.delete(row)
			db.commit()
			return True
		finally:
			db.close()

	ORDER_STATUS_HISTORY.pop(order_id, None)
	return ORDERS.pop(order_id, None) is not None


def add_status_history(order_id: str, previous_status: str, new_status: OrderStatus) -> None:
	entry = StatusHistoryEntry(
		order_id=order_id,
		previous_status=previous_status,
		new_status=new_status,
		changed_at=datetime.now(UTC),
	)

	if _backend() == "sqlite":
		db = SessionLocal()
		try:
			db.add(
				OrderStatusHistoryDB(
					order_id=entry.order_id,
					previous_status=entry.previous_status,
					new_status=entry.new_status.value,
					changed_at=entry.changed_at,
				)
			)
			db.commit()
		finally:
			db.close()
		return

	ORDER_STATUS_HISTORY.setdefault(order_id, []).append(entry)


def get_status_history(order_id: str) -> List[StatusHistoryEntry]:
	if _backend() == "sqlite":
		db = SessionLocal()
		try:
			rows = (
				db.query(OrderStatusHistoryDB)
				.filter(OrderStatusHistoryDB.order_id == order_id)
				.order_by(OrderStatusHistoryDB.changed_at.asc())
				.all()
			)
			return [
				StatusHistoryEntry(
					order_id=row.order_id,
					previous_status=row.previous_status,
					new_status=OrderStatus(row.new_status),
					changed_at=row.changed_at,
				)
				for row in rows
			]
		finally:
			db.close()

	return ORDER_STATUS_HISTORY.get(order_id, [])


def clear_orders() -> None:
	if _backend() == "sqlite":
		db = SessionLocal()
		try:
			db.query(OrderStatusHistoryDB).delete()
			db.query(OrderDB).delete()
			db.commit()
		finally:
			db.close()
		return

	ORDERS.clear()
	ORDER_STATUS_HISTORY.clear()
