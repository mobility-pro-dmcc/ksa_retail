"""Stock availability per item / warehouse / inventory dimension.

on_hand   = sum of the Stock Ledger for the dimension values.
reserved  = undelivered quantity on submitted, open Sales Orders for the same item,
            warehouse and dimension values (supplier-delivered lines excluded).
available = on_hand - reserved (never negative).

Concurrency: before validating a sale or a delivery the matching `Bin` rows are locked
(`SELECT ... FOR UPDATE`), so two cashiers selling the last units of the same item are
serialised and the second one sees the first one's reservation.
"""

import frappe
from frappe import _
from frappe.utils import flt

from ksa_retail.pos import dimensions

EPSILON = 1e-6


def items_in_stock(warehouse: str | None) -> list[str]:
	"""Items with a positive quantity on hand in the warehouse."""
	if not warehouse:
		return []
	return frappe.get_all(
		"Bin", filters={"warehouse": warehouse, "actual_qty": [">", 0]}, pluck="item_code", distinct=True
	)


def get_stock(item_codes, warehouse: str) -> dict:
	"""{item_code: {dimension_key: {"on_hand", "reserved", "available"}}}"""
	item_codes = tuple(set(item_codes))
	if not item_codes or not warehouse:
		return {}
	dims = dimensions.get_dimensions()
	ledger_cols = "".join(f", `{d.target}`" for d in dims)
	result: dict = {}

	for row in frappe.db.sql(
		f"""select item_code{ledger_cols}, sum(actual_qty) as qty
		from `tabStock Ledger Entry`
		where is_cancelled = 0 and warehouse = %(warehouse)s and item_code in %(items)s
		group by item_code{ledger_cols}""",
		{"warehouse": warehouse, "items": item_codes},
		as_dict=True,
	):
		bucket_key = dimensions.key([row[d.target] for d in dims])
		result.setdefault(row.item_code, {})[bucket_key] = {"on_hand": flt(row.qty), "reserved": 0.0}

	order_cols = "".join(f", soi.`{d.source}`" if d.on_sales_order else ", NULL" for d in dims)
	order_group = "".join(f", soi.`{d.source}`" for d in dims if d.on_sales_order)
	for row in frappe.db.sql(
		f"""select soi.item_code{order_cols},
			sum((soi.qty - soi.delivered_qty) * soi.conversion_factor) as qty
		from `tabSales Order Item` soi join `tabSales Order` so on so.name = soi.parent
		where so.docstatus = 1 and so.status not in ('Closed', 'Completed')
			and soi.warehouse = %(warehouse)s and soi.item_code in %(items)s
			and ifnull(soi.delivered_by_supplier, 0) = 0 and soi.delivered_qty < soi.qty
		group by soi.item_code{order_group}""",
		{"warehouse": warehouse, "items": item_codes},
		as_list=True,
	):
		bucket_key = dimensions.key(row[1 : 1 + len(dims)])
		bucket = result.setdefault(row[0], {}).setdefault(bucket_key, {"on_hand": 0.0, "reserved": 0.0})
		bucket["reserved"] += flt(row[-1])

	for buckets in result.values():
		for bucket in buckets.values():
			bucket["available"] = max(0.0, bucket["on_hand"] - bucket["reserved"])
	return result


def bucket(stock: dict, item_code: str, dimension_key: tuple) -> dict:
	return (stock.get(item_code) or {}).get(dimension_key) or {
		"on_hand": 0.0,
		"reserved": 0.0,
		"available": 0.0,
	}


def lock_bins(item_codes, warehouse: str) -> None:
	"""Serialise concurrent stock-changing operations on the same items."""
	item_codes = sorted(set(item_codes))  # fixed order: no deadlocks between two sales
	if item_codes:
		frappe.db.sql(
			"select name from `tabBin` where warehouse = %s and item_code in %s order by item_code for update",
			(warehouse, tuple(item_codes)),
		)


def is_stock_item(item_code: str) -> bool:
	return bool(frappe.get_cached_value("Item", item_code, "is_stock_item"))


def validate_order_availability(order, warehouse: str) -> None:
	"""A new Sales Order must not ask for more than is available per dimension."""
	requested: dict = {}
	for row in order.items:
		if row.get("delivered_by_supplier") or not is_stock_item(row.item_code):
			continue
		bucket_key = (row.item_code, dimensions.key_of(row))
		requested[bucket_key] = requested.get(bucket_key, 0) + flt(row.qty) * flt(row.conversion_factor or 1)
	if not requested:
		return

	codes = {code for code, _key in requested}
	lock_bins(codes, warehouse)
	stock = get_stock(codes, warehouse)
	for (code, dimension_key), qty in requested.items():
		available = bucket(stock, code, dimension_key)["available"]
		if qty > available + EPSILON:
			frappe.throw(
				_("Only {0} of {1} ({2}) available in {3}, requested {4}.").format(
					frappe.format(available, "Float"),
					code,
					dimensions.describe(dimension_key),
					warehouse,
					frappe.format(qty, "Float"),
				),
				title=_("Insufficient Stock"),
			)


def validate_delivery_stock(delivery_note) -> None:
	"""Enough stock on hand, per dimension, for every line of a Delivery Note."""
	needed: dict = {}
	for row in delivery_note.items:
		if not is_stock_item(row.item_code):
			continue
		bucket_key = (row.item_code, row.warehouse, dimensions.key_of(row))
		needed[bucket_key] = needed.get(bucket_key, 0) + flt(row.stock_qty or row.qty)

	by_warehouse: dict = {}
	for code, warehouse, _key in needed:
		by_warehouse.setdefault(warehouse, set()).add(code)
	stock_by_warehouse = {}
	for warehouse, codes in by_warehouse.items():
		lock_bins(codes, warehouse)
		stock_by_warehouse[warehouse] = get_stock(codes, warehouse)

	for (code, warehouse, dimension_key), qty in needed.items():
		on_hand = bucket(stock_by_warehouse[warehouse], code, dimension_key)["on_hand"]
		if qty > on_hand + EPSILON:
			frappe.throw(
				_("Not enough stock to deliver {0} ({1}) from {2}: {3} on hand, {4} needed.").format(
					code,
					dimensions.describe(dimension_key),
					warehouse,
					frappe.format(on_hand, "Float"),
					frappe.format(qty, "Float"),
				),
				title=_("Insufficient Stock"),
			)


def batches_for(item_code: str, warehouse: str, dimension_values: list) -> list[tuple[str, float]]:
	"""Batches holding stock of this item in this warehouse *for these dimension values*,
	oldest first. ERPNext's automatic FIFO picking ignores inventory dimensions, so a
	2024 order could otherwise ship 2025 tyres."""
	condition, params = "", {"item": item_code, "warehouse": warehouse}
	for dimension, value in zip(dimensions.get_dimensions(), dimension_values, strict=False):
		condition += f" and ifnull(sle.`{dimension.target}`, '') = %({dimension.target})s"
		params[dimension.target] = value or ""
	rows = frappe.db.sql(
		f"""select batch_no, sum(qty) as qty, min(first_in) as first_in from (
			select sbe.batch_no, sbe.qty, sle.posting_datetime as first_in
			from `tabStock Ledger Entry` sle
			join `tabSerial and Batch Entry` sbe on sbe.parent = sle.serial_and_batch_bundle
			where sle.is_cancelled = 0 and sle.item_code = %(item)s and sle.warehouse = %(warehouse)s
				and ifnull(sbe.batch_no, '') != '' {condition}
			union all
			select sle.batch_no, sle.actual_qty, sle.posting_datetime
			from `tabStock Ledger Entry` sle
			where sle.is_cancelled = 0 and sle.item_code = %(item)s and sle.warehouse = %(warehouse)s
				and ifnull(sle.serial_and_batch_bundle, '') = '' and ifnull(sle.batch_no, '') != '' {condition}
		) t group by batch_no having sum(qty) > 0 order by first_in, batch_no""",
		params,
		as_dict=True,
	)
	return [(r.batch_no, flt(r.qty)) for r in rows]


def assign_batches(delivery_note) -> None:
	"""Split batch-tracked lines across batches of the selected dimension values."""
	if not frappe.get_meta("Delivery Note Item").has_field("use_serial_batch_fields"):
		return  # older ERPNext: standard batch selection
	dims = dimensions.get_dimensions()
	new_rows, taken = [], {}
	for row in delivery_note.items:
		needs_batch = frappe.get_cached_value("Item", row.item_code, "has_batch_no")
		if not needs_batch or row.get("batch_no") or row.get("serial_and_batch_bundle"):
			new_rows.append(row.as_dict(no_default_fields=True))
			continue
		factor = flt(row.conversion_factor) or 1
		need = flt(row.qty) * factor
		dimension_values = [row.get(d.source) for d in dims]
		parts = []
		for batch_no, qty in batches_for(row.item_code, row.warehouse, dimension_values):
			qty -= taken.get(batch_no, 0)
			if qty <= 0 or need <= EPSILON:
				continue
			use = min(qty, need)
			taken[batch_no] = taken.get(batch_no, 0) + use
			parts.append((batch_no, use))
			need -= use
		if need > EPSILON:
			frappe.throw(
				_("Not enough batch stock of {0} ({1}) in {2}.").format(
					row.item_code, dimensions.describe(dimensions.key(dimension_values)), row.warehouse
				),
				title=_("Insufficient Stock"),
			)
		for batch_no, qty in parts:
			split = frappe._dict(row.as_dict(no_default_fields=True))
			split.update(
				{"batch_no": batch_no, "use_serial_batch_fields": 1, "qty": qty / factor, "stock_qty": qty}
			)
			split.pop("serial_and_batch_bundle", None)
			new_rows.append(split)
	delivery_note.set("items", [])
	for row in new_rows:
		delivery_note.append("items", row)
