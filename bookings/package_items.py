"""Package item trees shared by booking PDF and supplier-field API."""

from __future__ import annotations

from packages.models import PackageItem, PackagePrice


def _package_items_by_parent(
    package_price: PackagePrice,
    *,
    include_inactive: bool = False,
) -> dict[int | None, list[PackageItem]]:
    item_qs = PackageItem.objects.filter(
        package_price_id=package_price.pk,
        deleted_at__isnull=True,
    )
    if not include_inactive:
        item_qs = item_qs.filter(is_active=True)
    by_parent: dict[int | None, list[PackageItem]] = {}
    for item in item_qs:
        by_parent.setdefault(item.parent_id, []).append(item)
    for children in by_parent.values():
        children.sort(key=lambda x: (x.sort_order, x.id, x.title))
    return by_parent


def flat_package_item_rows(
    package_price: PackagePrice,
    *,
    include_inactive: bool = False,
) -> list[tuple[int, str]]:
    """Package item rows as ``(depth, title)`` for PDF (tree order). Depth 0 = root."""
    by_parent = _package_items_by_parent(package_price, include_inactive=include_inactive)
    rows: list[tuple[int, str]] = []

    def walk(parent_id: int | None, depth: int) -> None:
        for item in by_parent.get(parent_id, []):
            title = (item.title or '').strip() or '—'
            rows.append((depth, title))
            walk(item.pk, depth + 1)

    walk(None, 0)
    return rows


def nested_package_items_for_api(
    package_price: PackagePrice,
    *,
    include_inactive: bool = False,
) -> list[dict]:
    """Nested package items for JSON APIs (same source rows as booking PDF)."""
    by_parent = _package_items_by_parent(package_price, include_inactive=include_inactive)

    def node(item: PackageItem) -> dict:
        children = by_parent.get(item.pk, [])
        return {
            'id': item.id,
            'title': item.title,
            'price': item.price,
            'is_active': item.is_active,
            'children': [node(child) for child in children],
        }

    return [node(item) for item in by_parent.get(None, [])]
