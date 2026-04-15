from sqlalchemy import select

from app.aris3.db.models import DrawerEvent
from tests.pos_sales_helpers import create_tenant_user, login, seed_defaults


def test_create_drawer_event_and_confirm_close(client, db_session):
    tenant, store, _other_store, user = create_tenant_user(db_session, suffix="drawer-events")
    seed_defaults(db_session)
    token = login(client, username=user.username, password="Pass1234!")

    create_resp = client.post(
        "/aris3/pos/drawer/events",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "tenant_id": str(tenant.id),
            "store_id": str(store.id),
            "terminal_id": "TERM-01",
            "cash_session_id": None,
            "sale_id": None,
            "movement_type": "MANUAL",
            "event_type": "MANUAL_DRAWER_OPEN",
            "reason": "Need change",
            "printer_name": "POS58",
            "machine_name": "FrontDesk-1",
            "result": "SUCCESS",
            "details_json": {"phase": 1},
        },
    )
    assert create_resp.status_code == 200
    payload = create_resp.json()
    assert payload["event_type"] == "MANUAL_DRAWER_OPEN"
    assert payload["closed_confirmed_at"] is None

    confirm_resp = client.post(
        f"/aris3/pos/drawer/events/{payload['id']}/actions",
        headers={"Authorization": f"Bearer {token}"},
        json={"action": "CONFIRM_CLOSE", "tenant_id": str(tenant.id), "store_id": str(store.id)},
    )
    assert confirm_resp.status_code == 200
    confirmed = confirm_resp.json()
    assert confirmed["closed_confirmed_at"] is not None

    rows = db_session.execute(
        select(DrawerEvent).where(
            DrawerEvent.tenant_id == tenant.id,
            DrawerEvent.store_id == store.id,
        )
    ).scalars().all()
    assert len(rows) == 2
    assert any(row.event_type == "DRAWER_CLOSE_CONFIRMED" for row in rows)


def test_confirm_close_not_found(client, db_session):
    tenant, store, _other_store, user = create_tenant_user(db_session, suffix="drawer-events-not-found")
    seed_defaults(db_session)
    token = login(client, username=user.username, password="Pass1234!")

    resp = client.post(
        "/aris3/pos/drawer/events/00000000-0000-0000-0000-000000000999/actions",
        headers={"Authorization": f"Bearer {token}"},
        json={"action": "CONFIRM_CLOSE", "tenant_id": str(tenant.id), "store_id": str(store.id)},
    )
    assert resp.status_code == 404
    assert resp.json()["code"] == "RESOURCE_NOT_FOUND"
