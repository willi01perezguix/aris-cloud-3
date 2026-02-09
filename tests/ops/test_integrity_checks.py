import uuid
from datetime import datetime, date

from app.aris3.db.models import (
    PosCashSession,
    PosSale,
    PosSaleLine,
    StockItem,
    Store,
    Tenant,
    Transfer,
)
from app.ops.integrity_checks import (
    check_cash_session_open,
    check_duplicate_epc,
    check_non_reusable_label_reuse,
    check_paid_sale_totals,
    check_total_vendible_status,
    check_transfer_fsm,
)


def _seed_tenant_store(db_session):
    tenant = Tenant(id=uuid.uuid4(), name="Tenant Ops")
    store = Store(id=uuid.uuid4(), tenant_id=tenant.id, name="Store Ops")
    db_session.add_all([tenant, store])
    db_session.commit()
    return tenant, store


def test_total_vendible_status_ok(db_session):
    tenant, _store = _seed_tenant_store(db_session)
    db_session.add(
        StockItem(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            status="RFID",
            location_code="BODEGA",
            location_is_vendible=True,
        )
    )
    db_session.commit()
    findings = check_total_vendible_status(db_session, str(tenant.id))
    assert findings == []


def test_total_vendible_status_violation(db_session):
    tenant, _store = _seed_tenant_store(db_session)
    db_session.add(
        StockItem(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            status="SOLD",
            location_code="STORE",
            location_is_vendible=True,
        )
    )
    db_session.commit()
    findings = check_total_vendible_status(db_session, str(tenant.id))
    assert len(findings) == 1


def test_duplicate_epc_ok(db_session):
    tenant, _store = _seed_tenant_store(db_session)
    db_session.add(
        StockItem(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            status="RFID",
            epc="ABCDEF123456ABCDEF123456",
        )
    )
    db_session.commit()
    findings = check_duplicate_epc(db_session, str(tenant.id))
    assert findings == []


def test_duplicate_epc_violation(db_session):
    tenant, _store = _seed_tenant_store(db_session)
    epc = "ABCDEF123456ABCDEF123456"
    epc_variant = "ABCD-EF123456ABCDEF123456"
    db_session.add_all(
        [
            StockItem(id=uuid.uuid4(), tenant_id=tenant.id, status="RFID", epc=epc),
            StockItem(id=uuid.uuid4(), tenant_id=tenant.id, status="RFID", epc=epc_variant),
        ]
    )
    db_session.commit()
    findings = check_duplicate_epc(db_session, str(tenant.id))
    assert len(findings) == 1


def test_non_reusable_label_reuse_ok(db_session):
    tenant, store = _seed_tenant_store(db_session)
    sale = PosSale(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        store_id=store.id,
        status="PAID",
        total_due=10.0,
        paid_total=10.0,
        balance_due=0.0,
        change_due=0.0,
    )
    db_session.add(sale)
    db_session.add(
        PosSaleLine(
            id=uuid.uuid4(),
            sale_id=sale.id,
            tenant_id=tenant.id,
            line_type="EPC",
            status="NON_REUSABLE_LABEL",
            epc="ABCDEF123456ABCDEF123456",
        )
    )
    db_session.add(
        StockItem(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            status="SOLD",
            epc="ABCDEF123456ABCDEF123456",
        )
    )
    db_session.commit()
    findings = check_non_reusable_label_reuse(db_session, str(tenant.id))
    assert findings == []


def test_non_reusable_label_reuse_violation(db_session):
    tenant, store = _seed_tenant_store(db_session)
    epc = "ABCDEF123456ABCDEF123456"
    sale = PosSale(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        store_id=store.id,
        status="PAID",
        total_due=10.0,
        paid_total=10.0,
        balance_due=0.0,
        change_due=0.0,
    )
    db_session.add(sale)
    db_session.add(
        PosSaleLine(
            id=uuid.uuid4(),
            sale_id=sale.id,
            tenant_id=tenant.id,
            line_type="EPC",
            status="NON_REUSABLE_LABEL",
            epc=epc,
        )
    )
    db_session.add(
        StockItem(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            status="RFID",
            epc=epc,
        )
    )
    db_session.commit()
    findings = check_non_reusable_label_reuse(db_session, str(tenant.id))
    assert len(findings) == 1


def test_cash_session_open_ok(db_session):
    tenant, store = _seed_tenant_store(db_session)
    db_session.add(
        PosCashSession(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            store_id=store.id,
            cashier_user_id=uuid.uuid4(),
            status="OPEN",
            business_date=date.today(),
            timezone="UTC",
        )
    )
    db_session.commit()
    findings = check_cash_session_open(db_session, str(tenant.id))
    assert findings == []


def test_cash_session_open_violation(db_session):
    tenant, store = _seed_tenant_store(db_session)
    cashier = uuid.uuid4()
    db_session.add_all(
        [
            PosCashSession(
                id=uuid.uuid4(),
                tenant_id=tenant.id,
                store_id=store.id,
                cashier_user_id=cashier,
                status="OPEN",
                business_date=date.today(),
                timezone="UTC",
            ),
            PosCashSession(
                id=uuid.uuid4(),
                tenant_id=tenant.id,
                store_id=store.id,
                cashier_user_id=cashier,
                status="OPEN",
                business_date=date.today(),
                timezone="UTC",
            ),
        ]
    )
    db_session.commit()
    findings = check_cash_session_open(db_session, str(tenant.id))
    assert len(findings) == 1


def test_paid_sale_totals_ok(db_session):
    tenant, store = _seed_tenant_store(db_session)
    db_session.add(
        PosSale(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            store_id=store.id,
            status="PAID",
            total_due=10.0,
            paid_total=10.0,
            balance_due=0.0,
            change_due=0.0,
        )
    )
    db_session.commit()
    findings = check_paid_sale_totals(db_session, str(tenant.id))
    assert findings == []


def test_paid_sale_totals_violation(db_session):
    tenant, store = _seed_tenant_store(db_session)
    db_session.add(
        PosSale(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            store_id=store.id,
            status="PAID",
            total_due=10.0,
            paid_total=8.0,
            balance_due=2.0,
            change_due=0.0,
        )
    )
    db_session.commit()
    findings = check_paid_sale_totals(db_session, str(tenant.id))
    assert len(findings) == 1


def test_transfer_fsm_ok(db_session):
    tenant, store = _seed_tenant_store(db_session)
    db_session.add(
        Transfer(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            origin_store_id=store.id,
            destination_store_id=store.id,
            status="DISPATCHED",
            dispatched_at=datetime.utcnow(),
        )
    )
    db_session.commit()
    findings = check_transfer_fsm(db_session, str(tenant.id))
    assert findings == []


def test_transfer_fsm_violation(db_session):
    tenant, store = _seed_tenant_store(db_session)
    db_session.add(
        Transfer(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            origin_store_id=store.id,
            destination_store_id=store.id,
            status="RECEIVED",
            dispatched_at=datetime.utcnow(),
            received_at=None,
        )
    )
    db_session.commit()
    findings = check_transfer_fsm(db_session, str(tenant.id))
    assert len(findings) == 1
