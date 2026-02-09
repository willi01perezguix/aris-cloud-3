import uuid

from app.aris3.core.error_catalog import ErrorCatalog
from app.aris3.db.models import Store
from tests.pos_sales_helpers import (
    create_tenant_user,
    login,
    sale_line,
    sale_payload,
    seed_defaults,
)


def test_pos_sale_tenant_and_store_boundaries(client, db_session):
    seed_defaults(db_session)
    tenant_a, store_a, _other_store_a, user_a = create_tenant_user(db_session, suffix="pos-boundary-a")
    tenant_b, store_b, _other_store_b, user_b = create_tenant_user(db_session, suffix="pos-boundary-b")

    token_a = login(client, user_a.username, "Pass1234!")
    payload = sale_payload(
        str(store_a.id),
        [
            sale_line(
                line_type="SKU",
                qty=1,
                unit_price=5.0,
                sku="SKU-1",
                epc=None,
                status="PENDING",
            )
        ],
        transaction_id="txn-boundary",
    )
    create_response = client.post(
        "/aris3/pos/sales",
        headers={"Authorization": f"Bearer {token_a}", "Idempotency-Key": "pos-sale-boundary"},
        json=payload,
    )
    assert create_response.status_code == 201
    sale_id = create_response.json()["header"]["id"]

    token_b = login(client, user_b.username, "Pass1234!")
    cross_tenant_response = client.get(
        f"/aris3/pos/sales/{sale_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert cross_tenant_response.status_code == 403
    assert cross_tenant_response.json()["code"] == ErrorCatalog.CROSS_TENANT_ACCESS_DENIED.code

    user_c = create_tenant_user(db_session, suffix="pos-boundary-store", role="USER")[3]
    store_c = Store(id=uuid.uuid4(), tenant_id=tenant_a.id, name="Store A-Alt")
    db_session.add(store_c)
    db_session.flush()
    user_c.tenant_id = tenant_a.id
    user_c.store_id = store_c.id
    db_session.commit()
    token_c = login(client, user_c.username, "Pass1234!")
    store_scope_response = client.get(
        f"/aris3/pos/sales/{sale_id}",
        headers={"Authorization": f"Bearer {token_c}"},
    )
    assert store_scope_response.status_code == 403


def test_pos_sale_rbac_denied(client, db_session):
    seed_defaults(db_session)
    _tenant, store, _other_store, user = create_tenant_user(db_session, suffix="pos-rbac", role="USER")
    token = login(client, user.username, "Pass1234!")

    payload = sale_payload(
        str(store.id),
        [
            sale_line(
                line_type="SKU",
                qty=1,
                unit_price=5.0,
                sku="SKU-1",
                epc=None,
                status="PENDING",
            )
        ],
        transaction_id="txn-rbac",
    )
    response = client.post(
        "/aris3/pos/sales",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "pos-sale-rbac"},
        json=payload,
    )
    assert response.status_code == 403
    assert response.json()["code"] == ErrorCatalog.PERMISSION_DENIED.code
