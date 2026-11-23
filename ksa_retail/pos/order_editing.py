"""Editing a submitted Sales Order that has no invoice yet.

Uses ERPNext's own "Update Items" (update_child_qty_rate), so payments stay linked to the
same order. If the edit touches delivered lines, the order's Delivery Notes are cancelled
first and the still-wanted delivered quantity is delivered again with a new one.
"""

import json

import frappe
from frappe import _
from frappe.utils import cstr, flt, nowdate

from ksa_retail.pos import catalog, dimensions, order_summary, stock
from ksa_retail.pos.context import get_context, require_warehouse
from ksa_retail.pos.fulfilment import deliver_order
from ksa_retail.pos.inputs import SaleLine

EPSILON = 1e-6


def update_order(order_name: str, lines: list[SaleLine]) -> list[tuple]:
	from erpnext.controllers.accounts_controller import update_child_qty_rate

	order = frappe.get_doc("Sales Order", order_name)
	order.check_permission("write")
	frappe.has_permission("Sales Order", "submit", doc=order, throw=True)
	reason = order_summary.edit_block_reason(order)
	if reason:
		frappe.throw(reason, title=_("Cannot Edit"))
	if not lines:
		frappe.throw(_("An order needs at least one item. Close the order in ERPNext to cancel it."))

	previous = {row.name: row for row in order.items}
	previous_key = {row.name: (row.item_code, dimensions.key_of(row)) for row in order.items}
	_keep_identity_only_if_unchanged(lines, previous_key)

	kept = {line.so_detail: line for line in lines if line.so_detail}
	touches_delivery = any(
		flt(row.delivered_qty) > 0 and (row.name not in kept or kept[row.name].qty < flt(row.delivered_qty))
		for row in order.items
	)
	delivered_before = _delivered_by_key(order, previous_key)

	created: list[tuple] = []
	if touches_delivery:
		created += _cancel_deliveries(order_name)
		order.reload()

	_validate_new_quantities(order, lines, previous_key)
	update_child_qty_rate(
		"Sales Order", json.dumps(_update_rows(order, lines, previous), default=str), order_name
	)
	_set_dimensions_on_new_rows(order_name, previous, lines)

	if touches_delivery and delivered_before:
		created += _deliver_again(order_name, delivered_before)

	frappe.get_doc("Sales Order", order_name).add_comment("Info", _("Edited from KSA Retail POS"))
	return created


def _keep_identity_only_if_unchanged(lines: list[SaleLine], previous_key: dict) -> None:
	"""A line keeps its order row only if item and dimension values are unchanged."""
	for line in lines:
		if line.so_detail and previous_key.get(line.so_detail) != (
			line.item_code,
			dimensions.key_from_values(line.dims),
		):
			line.so_detail = None


def _delivered_by_key(order, previous_key: dict) -> dict:
	delivered = {}
	for row in order.items:
		if flt(row.delivered_qty) > 0 and not row.delivered_by_supplier:
			key = previous_key[row.name]
			delivered[key] = delivered.get(key, 0) + flt(row.delivered_qty)
	return delivered


def _cancel_deliveries(order_name: str) -> list[tuple]:
	cancelled = []
	for name in frappe.db.sql_list(
		"""select distinct dn.name from `tabDelivery Note` dn
		join `tabDelivery Note Item` dni on dni.parent = dn.name
		where dni.against_sales_order = %s and dn.docstatus = 1 order by dn.creation desc""",
		order_name,
	):
		frappe.get_doc("Delivery Note", name).cancel()
		cancelled.append(("Delivery Note", name, "cancelled"))
	return cancelled


def _validate_new_quantities(order, lines: list[SaleLine], previous_key: dict) -> None:
	"""This order's own reservation counts as available for its new quantities."""
	warehouse = require_warehouse()
	still_delivered, own_pending = {}, {}
	for row in order.items:
		key = previous_key[row.name]
		still_delivered[key] = still_delivered.get(key, 0) + flt(row.delivered_qty)
		if not row.delivered_by_supplier:
			own_pending[key] = own_pending.get(key, 0) + (flt(row.qty) - flt(row.delivered_qty)) * flt(
				row.conversion_factor or 1
			)
	wanted = {}
	for line in lines:
		key = (line.item_code, dimensions.key_from_values(line.dims))
		wanted[key] = wanted.get(key, 0) + line.qty

	codes = {code for code, _key in wanted}
	stock.lock_bins(codes, warehouse)
	availability = stock.get_stock(codes, warehouse)
	for (code, dimension_key), qty in wanted.items():
		if not stock.is_stock_item(code):
			continue
		need = qty - still_delivered.get((code, dimension_key), 0)
		available = stock.bucket(availability, code, dimension_key)["available"] + own_pending.get(
			(code, dimension_key), 0
		)
		if need > available + EPSILON:
			frappe.throw(
				_("Only {0} of {1} ({2}) available, requested {3}.").format(
					frappe.format(available, "Float"),
					code,
					dimensions.describe(dimension_key),
					frappe.format(need, "Float"),
				),
				title=_("Insufficient Stock"),
			)


def _update_rows(order, lines: list[SaleLine], previous: dict) -> list[dict]:
	warehouse = require_warehouse()
	rows = []
	for line in lines:
		row = {
			"item_code": line.item_code,
			"qty": line.qty,
			"delivery_date": cstr(order.delivery_date or nowdate()),
		}
		if line.so_detail:
			old = previous[line.so_detail]
			row.update(
				{
					"docname": line.so_detail,
					"rate": line.rate if line.rate is not None else flt(old.rate),
					"uom": old.uom,
					"conversion_factor": old.conversion_factor,
					"warehouse": old.warehouse,
				}
			)
		else:
			rate = (
				line.rate
				if line.rate is not None
				else catalog.selling_price(line.item_code, order.selling_price_list)
			)
			row.update({"rate": flt(rate), "warehouse": warehouse})
		rows.append(row)
	return rows


def _set_dimensions_on_new_rows(order_name: str, previous: dict, lines: list[SaleLine]) -> None:
	"""Update Items does not carry custom fields: set dimension values on the new rows."""
	order = frappe.get_doc("Sales Order", order_name)
	new_rows = [row for row in order.items if row.name not in previous]
	new_lines = [line for line in lines if not line.so_detail]
	for row, line in zip(new_rows, new_lines, strict=False):
		for dimension in dimensions.order_line_dimensions():
			value = line.dims.get(dimension.source)
			if value:
				frappe.db.set_value(
					"Sales Order Item", row.name, dimension.source, value, update_modified=False
				)


def _deliver_again(order_name: str, delivered_before: dict) -> list[tuple]:
	"""Deliver again what was delivered before the edit, capped at the new quantities."""
	order = frappe.get_doc("Sales Order", order_name)
	quantities, left = {}, dict(delivered_before)
	for row in order.items:
		key = (row.item_code, dimensions.key_of(row))
		qty = min(flt(row.qty) - flt(row.delivered_qty), left.get(key, 0))
		if qty > 0:
			quantities[row.name] = qty
			left[key] -= qty
	return deliver_order(order_name, quantities) if quantities else []
