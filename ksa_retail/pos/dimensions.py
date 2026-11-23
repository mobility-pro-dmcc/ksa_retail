"""Inventory Dimensions (e.g. Production Year, Tire Size) as the POS uses them.

`source` is the field on transaction lines (Sales Order Item / Delivery Note Item ...),
`target` the field on Stock Ledger Entry. Only dimensions that exist on the Stock Ledger
are usable for availability; `on_sales_order` tells whether the order line can carry it
(the app adds that field on migrate / when a dimension is created).
"""

import frappe
from frappe import _
from frappe.utils import cstr

from ksa_retail.setup.install import get_inventory_dimensions

_CACHE_ATTR = "ksa_pos_dimensions"


def get_dimensions() -> list[frappe._dict]:
	cached = getattr(frappe.local, _CACHE_ATTR, None)
	if cached is not None:
		return cached

	ledger = frappe.get_meta("Stock Ledger Entry")
	order_line = frappe.get_meta("Sales Order Item")
	dimensions = [
		frappe._dict(
			source=d.source_fieldname,
			target=d.target_fieldname,
			label=d.dimension_name,
			reference_doctype=d.reference_document,
			on_sales_order=order_line.has_field(d.source_fieldname),
			required=bool(d.get("reqd")),
		)
		for d in get_inventory_dimensions()
		if ledger.has_field(d.target_fieldname)
	]
	setattr(frappe.local, _CACHE_ATTR, dimensions)
	return dimensions


def clear_cache() -> None:
	if hasattr(frappe.local, _CACHE_ATTR):
		delattr(frappe.local, _CACHE_ATTR)


def source_fields() -> set[str]:
	return {d.source for d in get_dimensions()}


def order_line_dimensions() -> list[frappe._dict]:
	return [d for d in get_dimensions() if d.on_sales_order]


def key(values) -> tuple[str, ...]:
	"""Normalised dimension key: empty / None values compare equal."""
	return tuple(cstr(v or "") for v in values)


def key_of(row) -> tuple[str, ...]:
	"""Dimension key of a document row (or dict with dimension fields)."""
	return key([row.get(d.source) for d in get_dimensions()])


def key_from_values(values: dict | None) -> tuple[str, ...]:
	values = values or {}
	return key([values.get(d.source) for d in get_dimensions()])


def describe(dimension_key: tuple[str, ...]) -> str:
	return " / ".join(v for v in dimension_key if v) or _("no dimension")


def values_of(row) -> dict:
	"""{fieldname: value} of the dimensions the order line carries."""
	return {d.source: row.get(d.source) for d in order_line_dimensions()}


def allowed_values(fieldname: str) -> list[str]:
	dimension = next((d for d in get_dimensions() if d.source == fieldname), None)
	if not dimension:
		return []
	return frappe.get_list(
		dimension.reference_doctype, pluck="name", order_by="name desc", limit_page_length=100
	)
