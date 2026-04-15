from fastapi.testclient import TestClient
from datetime import date, timedelta

from app.storage import clear_orders, get_order, save_order
from main import app

client = TestClient(app)


def setup_function() -> None:
    clear_orders()


def test_create_order_and_defaults() -> None:
    payload = {
        "customer_name": "Ravi Kumar",
        "phone_number": "+91 9876543210",
        "garments": [
            {"type": "shirt", "quantity": 2},
            {"type": "pants", "quantity": 1},
        ],
    }

    response = client.post("/orders", json=payload)
    assert response.status_code == 201

    body = response.json()
    assert body["customer_name"] == "Ravi Kumar"
    assert body["status"] == "RECEIVED"
    assert body["total_bill"] == 35
    assert "estimated_delivery_date" in body
    assert len(body["order_id"]) > 0


def test_update_order_status() -> None:
    create_payload = {
        "customer_name": "Asha",
        "phone_number": "9999999999",
        "garments": [{"type": "saree", "quantity": 1}],
    }

    created = client.post("/orders", json=create_payload).json()
    order_id = created["order_id"]

    response = client.patch(f"/orders/{order_id}/status", json={"status": "PROCESSING"})
    assert response.status_code == 200
    assert response.json()["status"] == "PROCESSING"


def test_order_filters_and_dashboard() -> None:
    client.post(
        "/orders",
        json={
            "customer_name": "Ravi",
            "phone_number": "1111111111",
            "garments": [{"type": "shirt", "quantity": 1}],
        },
    )
    o2 = client.post(
        "/orders",
        json={
            "customer_name": "Meena",
            "phone_number": "2222222222",
            "garments": [{"type": "pants", "quantity": 2}],
        },
    ).json()

    client.patch(f"/orders/{o2['order_id']}/status", json={"status": "PROCESSING"})
    client.patch(f"/orders/{o2['order_id']}/status", json={"status": "READY"})

    by_name = client.get("/orders", params={"customer_name": "ravi"})
    assert by_name.status_code == 200
    assert len(by_name.json()) == 1

    by_status = client.get("/orders", params={"status": "READY"})
    assert by_status.status_code == 200
    assert len(by_status.json()) == 1

    dashboard = client.get("/dashboard")
    assert dashboard.status_code == 200
    body = dashboard.json()
    assert body["total_orders"] == 2
    assert body["total_revenue"] == 40
    assert body["orders_per_status"]["RECEIVED"] == 1
    assert body["orders_per_status"]["READY"] == 1


def test_invalid_order_id() -> None:
    response = client.patch("/orders/not-found/status", json={"status": "DELIVERED"})
    assert response.status_code == 404


def test_invalid_garment_type() -> None:
    response = client.post(
        "/orders",
        json={
            "customer_name": "Kiran",
            "phone_number": "1234567890",
            "garments": [{"type": "jacket", "quantity": 1}],
        },
    )
    assert response.status_code == 422


def test_get_order_by_id_and_delete_order() -> None:
    created = client.post(
        "/orders",
        json={
            "customer_name": "Neha",
            "phone_number": "5555555555",
            "garments": [{"type": "shirt", "quantity": 1}],
        },
    ).json()

    order_id = created["order_id"]

    fetched = client.get(f"/orders/{order_id}")
    assert fetched.status_code == 200
    assert fetched.json()["order_id"] == order_id

    deleted = client.delete(f"/orders/{order_id}")
    assert deleted.status_code == 200
    assert deleted.json()["order_id"] == order_id

    not_found = client.get(f"/orders/{order_id}")
    assert not_found.status_code == 404


def test_filter_by_garment_type_and_pagination() -> None:
    client.post(
        "/orders",
        json={
            "customer_name": "A",
            "phone_number": "1010101010",
            "garments": [{"type": "shirt", "quantity": 1}],
        },
    )
    client.post(
        "/orders",
        json={
            "customer_name": "B",
            "phone_number": "2020202020",
            "garments": [{"type": "pants", "quantity": 1}],
        },
    )
    client.post(
        "/orders",
        json={
            "customer_name": "C",
            "phone_number": "3030303030",
            "garments": [{"type": "shirt", "quantity": 2}],
        },
    )

    by_garment = client.get("/orders", params={"garment_type": "shirt"})
    assert by_garment.status_code == 200
    assert len(by_garment.json()) == 2

    paged = client.get("/orders", params={"skip": 1, "limit": 1})
    assert paged.status_code == 200
    assert len(paged.json()) == 1


def test_invalid_status_transition() -> None:
    created = client.post(
        "/orders",
        json={
            "customer_name": "Rina",
            "phone_number": "7777777777",
            "garments": [{"type": "saree", "quantity": 1}],
        },
    ).json()

    response = client.patch(
        f"/orders/{created['order_id']}/status",
        json={"status": "DELIVERED"},
    )
    assert response.status_code == 400


def test_order_status_history() -> None:
    created = client.post(
        "/orders",
        json={
            "customer_name": "History User",
            "phone_number": "9090909090",
            "garments": [{"type": "shirt", "quantity": 1}],
        },
    ).json()

    order_id = created["order_id"]
    client.patch(f"/orders/{order_id}/status", json={"status": "PROCESSING"})
    client.patch(f"/orders/{order_id}/status", json={"status": "READY"})

    history = client.get(f"/orders/{order_id}/history")
    assert history.status_code == 200
    body = history.json()
    assert len(body) == 3
    assert body[0]["previous_status"] == "CREATED"
    assert body[0]["new_status"] == "RECEIVED"
    assert body[1]["previous_status"] == "RECEIVED"
    assert body[1]["new_status"] == "PROCESSING"
    assert body[2]["previous_status"] == "PROCESSING"
    assert body[2]["new_status"] == "READY"


def test_garment_analytics_report() -> None:
    client.post(
        "/orders",
        json={
            "customer_name": "Ana",
            "phone_number": "1212121212",
            "garments": [{"type": "shirt", "quantity": 2}, {"type": "pants", "quantity": 1}],
        },
    )
    client.post(
        "/orders",
        json={
            "customer_name": "Bala",
            "phone_number": "3434343434",
            "garments": [{"type": "shirt", "quantity": 1}],
        },
    )

    report = client.get("/reports/garments")
    assert report.status_code == 200

    data = {item["garment_type"]: item for item in report.json()}
    assert data["shirt"]["total_quantity"] == 3
    assert data["shirt"]["total_revenue"] == 30
    assert data["pants"]["total_quantity"] == 1
    assert data["pants"]["total_revenue"] == 15


def test_delayed_orders_report() -> None:
    created = client.post(
        "/orders",
        json={
            "customer_name": "Late User",
            "phone_number": "5656565656",
            "garments": [{"type": "saree", "quantity": 1}],
        },
    ).json()

    order = get_order(created["order_id"])
    assert order is not None
    order.estimated_delivery_date = date.today() - timedelta(days=1)
    save_order(order)

    delayed = client.get("/reports/delayed")
    assert delayed.status_code == 200
    assert len(delayed.json()) == 1
    assert delayed.json()[0]["order_id"] == created["order_id"]
