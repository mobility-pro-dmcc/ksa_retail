"""Item search for the POS: configured search fields, selling price, stock per dimension."""

import frappe
from frappe import _
from frappe.utils import cint, cstr, flt, getdate

from ksa_retail.pos import dimensions, stock
from ksa_retail.pos.context import get_context

PAGE_SIZE = 24
MAX_PAGE_SIZE = 60
MAX_SPECS = 5
SPEC_FIELD_TYPES = ("Data", "Link", "Select", "Autocomplete", "Int", "Float")
CORE_ITEM_FIELDS = {
	"item_code",
	"item_name",
	"brand",
	"item_group",
	"stock_uom",
	"image",
	"description",
	"disabled",
}
# This app's own tyre fields on Item, always worth showing on the product card
OWN_ITEM_FIELDS = ("tire_size", "tire_pattern", "ply_rating")


def spec_fields(meta) -> list[str]:
	"""Short spec chips: fields marked In Preview / In List View, plus this app's tyre fields."""
	fields = []
	for df in meta.fields:
		if df.fieldname in CORE_ITEM_FIELDS or df.fieldtype not in SPEC_FIELD_TYPES:
			continue
		if (
			df.in_preview
			or df.in_list_view
			or df.get("module") == "Ksa Retail"
			or df.fieldname in OWN_ITEM_FIELDS
		):
			fields.append(df.fieldname)
	return fields[:MAX_SPECS]


def search_items(
	query: str = "",
	brand: str | None = None,
	start: int = 0,
	page_length: int = PAGE_SIZE,
	in_stock: int | bool = 0,
) -> dict:
	"""Sellable items; `in_stock` keeps only those with stock in the selected warehouse."""
	context = get_context()
	meta = frappe.get_meta("Item")
	query = cstr(query).strip()
	specs = spec_fields(meta)

	filters = {"disabled": 0, "has_variants": 0, "is_sales_item": 1}
	if brand:
		filters["brand"] = brand
	if cint(in_stock):
		stocked = stock.items_in_stock(context.warehouse)
		if not stocked:
			return {"items": [], "brands": brands() if not cint(start) else None}
		filters["name"] = ["in", stocked]
	or_filters = None
	if query:
		fields = {"name", "item_name", "brand", "item_group", *specs}
		fields |= {f.strip() for f in cstr(meta.search_fields).split(",") if f.strip()}
		or_filters = [[f, "like", f"%{query}%"] for f in sorted(fields) if f == "name" or meta.has_field(f)]

	items = frappe.get_list(
		"Item",
		fields=[
			"name as item_code",
			"item_name",
			"brand",
			"image",
			"stock_uom",
			"is_stock_item",
			"item_group",
			*specs,
		],
		filters=filters,
		or_filters=or_filters,
		order_by="item_name asc",
		start=cint(start),
		limit_page_length=min(cint(page_length) or PAGE_SIZE, MAX_PAGE_SIZE),
	)
	result = {"items": [], "brands": brands() if not cint(start) else None}
	if not items:
		return result

	codes = [i.item_code for i in items]
	prices = selling_prices(codes, context.price_list)
	availability = stock.get_stock(codes, context.warehouse)
	dimension_fields = [d.source for d in dimensions.get_dimensions()]
	labels = {f: _(meta.get_label(f)) for f in specs}

	for item in items:
		item.rate = flt(prices.get(item.item_code))
		item.specs = [{"label": labels[f], "value": item.pop(f)} for f in specs if item.get(f)]
		item.stock = [
			{"dims": dict(zip(dimension_fields, bucket_key, strict=False)), **bucket}
			for bucket_key, bucket in sorted((availability.get(item.item_code) or {}).items())
			if bucket["on_hand"] > 0 or bucket["available"] > 0
		]
	result["items"] = items
	return result


def selling_prices(item_codes: list[str], price_list: str | None) -> dict[str, float]:
	if not price_list or not item_codes:
		return {}
	today = getdate()
	prices = {}
	for row in frappe.get_all(
		"Item Price",
		filters={"price_list": price_list, "item_code": ["in", item_codes], "selling": 1},
		fields=["item_code", "price_list_rate", "valid_from", "valid_upto"],
		order_by="valid_from desc",
	):
		if row.valid_upto and getdate(row.valid_upto) < today:
			continue
		if row.valid_from and getdate(row.valid_from) > today:
			continue
		prices.setdefault(row.item_code, flt(row.price_list_rate))
	return prices


def selling_price(item_code: str, price_list: str | None) -> float:
	return selling_prices([item_code], price_list).get(item_code, 0.0)


def brands() -> list[str]:
	return frappe.get_list("Brand", pluck="name", order_by="name asc", limit_page_length=50)


def search_suppliers(query: str = "") -> list[dict]:
	query = cstr(query).strip()
	return frappe.get_list(
		"Supplier",
		filters={"disabled": 0},
		or_filters=[["name", "like", f"%{query}%"], ["supplier_name", "like", f"%{query}%"]]
		if query
		else None,
		fields=["name", "supplier_name"],
		limit_page_length=20,
	)
