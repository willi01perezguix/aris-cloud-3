from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select

from app.aris3.db.models import CatalogProduct, CatalogProductCostHistory, PreloadLine


def _normalize_key(value: str | None) -> str:
    return (value or "").strip().upper()


def _parse_date(value: str | date | None) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _parse_decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


@dataclass
class CatalogUpsertResult:
    catalog_product: CatalogProduct
    created: bool
    updated: bool
    review_required: bool


class CatalogProductService:
    def __init__(self, db):
        self.db = db

    def upsert_catalog_product(
        self,
        *,
        tenant_id: UUID,
        sku: str | None,
        variant_1: str | None,
        variant_2: str | None,
        description: str | None = None,
        brand: str | None = None,
        category: str | None = None,
        style: str | None = None,
        color: str | None = None,
        size: str | None = None,
        default_pool: str | None = None,
        default_location_code: str | None = None,
        sellable_default: bool = True,
        cost_gtq: Decimal | str | None = None,
        original_cost: Decimal | str | None = None,
        source_currency: str | None = None,
        exchange_rate_to_gtq: Decimal | str | None = None,
        suggested_price_gtq: Decimal | str | None = None,
        default_sale_price_gtq: Decimal | str | None = None,
        reference_price_original: Decimal | str | None = None,
        reference_price_gtq: Decimal | str | None = None,
        source_supplier: str | None = None,
        source_order_number: str | None = None,
        source_order_date: str | date | None = None,
        source_type: str = "MANUAL",
        source_extraction_id: UUID | None = None,
        source_preload_session_id: UUID | None = None,
        source_preload_line_id: UUID | None = None,
        created_by_user_id: UUID | None = None,
        update_sale_price: bool = False,
    ) -> CatalogUpsertResult:
        sku_value = (sku or "").strip()
        if not sku_value:
            sku_value = "UNSPECIFIED"
        normalized_sku = _normalize_key(sku_value)
        normalized_variant_1 = _normalize_key(variant_1)
        normalized_variant_2 = _normalize_key(variant_2)

        query = select(CatalogProduct).where(
            CatalogProduct.tenant_id == tenant_id,
            CatalogProduct.normalized_sku == normalized_sku,
            CatalogProduct.normalized_variant_1 == normalized_variant_1,
            CatalogProduct.normalized_variant_2 == normalized_variant_2,
        )
        product = self.db.execute(query).scalar_one_or_none()

        now = datetime.utcnow()
        created = False
        updated = False
        if product is None:
            product = CatalogProduct(
                tenant_id=tenant_id,
                sku=sku_value,
                normalized_sku=normalized_sku,
                variant_1=variant_1,
                variant_2=variant_2,
                normalized_variant_1=normalized_variant_1,
                normalized_variant_2=normalized_variant_2,
                created_at=now,
                updated_at=now,
                status="ACTIVE",
            )
            self.db.add(product)
            self.db.flush()
            created = True

        fields = {
            "description": description,
            "brand": brand,
            "category": category,
            "style": style,
            "variant_1": variant_1,
            "variant_2": variant_2,
            "normalized_variant_1": normalized_variant_1,
            "normalized_variant_2": normalized_variant_2,
            "color": color,
            "size": size,
            "default_pool": default_pool,
            "default_location_code": default_location_code,
            "sellable_default": sellable_default,
            "reference_price_original": _parse_decimal(reference_price_original),
            "reference_price_gtq": _parse_decimal(reference_price_gtq),
            "last_source_supplier": source_supplier,
            "last_source_order_number": source_order_number,
            "last_source_order_date": _parse_date(source_order_date),
        }
        for key, value in fields.items():
            if value is not None and getattr(product, key) != value:
                setattr(product, key, value)
                updated = True

        prev_last_cost = product.last_cost_gtq
        cost_value = _parse_decimal(cost_gtq)
        suggested_value = _parse_decimal(suggested_price_gtq)
        if cost_value is not None:
            product.last_cost_gtq = cost_value
            product.last_original_cost = _parse_decimal(original_cost)
            product.last_source_currency = source_currency
            product.last_exchange_rate_to_gtq = _parse_decimal(exchange_rate_to_gtq)
            if suggested_value is not None:
                product.suggested_price_gtq = suggested_value
            if default_sale_price_gtq is not None and (update_sale_price or product.default_sale_price_gtq is None):
                product.default_sale_price_gtq = _parse_decimal(default_sale_price_gtq)
            if prev_last_cost is not None and prev_last_cost != cost_value:
                product.price_review_required = True
            updated = True

            history = CatalogProductCostHistory(
                tenant_id=tenant_id,
                catalog_product_id=product.id,
                source_type=source_type,
                source_extraction_id=source_extraction_id,
                source_preload_session_id=source_preload_session_id,
                source_preload_line_id=source_preload_line_id,
                source_order_number=source_order_number,
                source_order_date=_parse_date(source_order_date),
                source_supplier=source_supplier,
                original_cost=_parse_decimal(original_cost),
                source_currency=source_currency,
                exchange_rate_to_gtq=_parse_decimal(exchange_rate_to_gtq),
                cost_gtq=cost_value,
                suggested_price_gtq=suggested_value,
                reference_price_original=_parse_decimal(reference_price_original),
                reference_price_gtq=_parse_decimal(reference_price_gtq),
                created_by_user_id=created_by_user_id,
                created_at=now,
            )
            self.db.add(history)

        product.updated_at = now
        return CatalogUpsertResult(
            catalog_product=product,
            created=created,
            updated=updated and not created,
            review_required=bool(product.price_review_required),
        )

    def upsert_catalog_product_from_preload_line(self, *, line: PreloadLine, created_by_user_id: UUID | None = None) -> CatalogUpsertResult:
        return self.upsert_catalog_product(
            tenant_id=line.tenant_id,
            sku=line.sku,
            variant_1=line.var1_value,
            variant_2=line.var2_value,
            description=line.description,
            default_pool=line.pool,
            default_location_code=line.location_code,
            sellable_default=line.vendible,
            cost_gtq=line.cost_price,
            suggested_price_gtq=line.suggested_price,
            default_sale_price_gtq=line.sale_price,
            source_type="PRELOAD",
            source_preload_session_id=line.preload_session_id,
            source_preload_line_id=line.id,
            created_by_user_id=created_by_user_id,
        )

    def upsert_catalog_products_from_ai_lines(
        self,
        *,
        tenant_id: UUID,
        lines: list[dict[str, Any]],
        source_extraction_id: UUID | None,
        store_id: UUID | None,
        created_by_user_id: UUID | None,
    ) -> tuple[list[CatalogUpsertResult], dict[str, int]]:
        _ = store_id
        results: list[CatalogUpsertResult] = []
        created_count = updated_count = review_count = 0
        for line in lines:
            result = self.upsert_catalog_product(
                tenant_id=tenant_id,
                sku=line.get("sku") or line.get("suggested_sku"),
                variant_1=line.get("variant_1"),
                variant_2=line.get("variant_2"),
                description=line.get("description"),
                brand=line.get("brand"),
                category=line.get("category"),
                style=line.get("style"),
                color=line.get("color"),
                size=line.get("size"),
                default_pool=line.get("pool"),
                default_location_code=line.get("location_code"),
                sellable_default=bool(line.get("sellable", True)),
                cost_gtq=line.get("cost_gtq"),
                original_cost=line.get("original_cost"),
                source_currency=line.get("source_currency"),
                exchange_rate_to_gtq=line.get("exchange_rate_to_gtq"),
                suggested_price_gtq=line.get("suggested_price_gtq"),
                reference_price_original=line.get("reference_price_original"),
                reference_price_gtq=line.get("reference_price_gtq"),
                source_supplier=line.get("source_supplier"),
                source_order_number=line.get("source_order_number"),
                source_order_date=line.get("source_order_date"),
                source_type="AI_PRELOAD",
                source_extraction_id=source_extraction_id,
                created_by_user_id=created_by_user_id,
            )
            results.append(result)
            created_count += int(result.created)
            updated_count += int(result.updated)
            review_count += int(result.review_required)
        return results, {
            "created_count": created_count,
            "updated_count": updated_count,
            "review_required_count": review_count,
        }
