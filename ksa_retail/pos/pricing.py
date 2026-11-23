"""Building Sales Orders from POS lines and reading their totals.

ERPNext computes every amount (price list rates, discounts, taxes, rounding); the POS
only sets what the cashier chose. The same builder serves the live quote shown while
the cashier works and the order that is finally submitted, so they always match.
"""

import frappe
from frappe import _
from frappe.utils import flt, nowdate

from ksa_retail.pos import dimensions, stock
from ksa_retail.pos.context import get_context, require_warehouse
from ksa_retail.pos.inputs import Discount, DropShip, SaleLine


def build_sales_order(
	customer: str,
	lines: list[SaleLine],
	discount: Discount | None = None,
	drop_ship: DropShip | None = None,
	validate_stock: bool = True,
):
	context = get_context()
	warehouse = require_warehouse()
	if not lines:
		frappe.throw(_("Add items to the sale."))

	order = frappe.new_doc("Sales Order")
	order.update(
		{
			"customer": customer,
			"company": context.company,
			"transaction_date": nowdate(),
			"delivery_date": nowdate(),
			"order_type": "Sales",
			"selling_price_list": context.price_list,
			"set_warehouse": warehouse,
		}
	)
	if context.tax_template:
		order.taxes_and_charges = context.tax_template

	supplier = drop_ship.supplier if drop_ship else None
	if drop_ship and not supplier:
		frappe.throw(_("Select the supplier who will deliver directly."))
	any_line_flagged = any(line.drop_ship for line in lines)

	for line in lines:
		row = order.append(
			"items",
			{
				"item_code": line.item_code,
				"qty": line.qty,
				"warehouse": warehouse,
				"delivery_date": nowdate(),
			},
		)
		for dimension in dimensions.order_line_dimensions():
			if line.dims.get(dimension.source):
				row.set(dimension.source, line.dims[dimension.source])
		if supplier and (line.drop_ship or not any_line_flagged):
			row.delivered_by_supplier = 1
			row.supplier = supplier
		elif line.drop_ship:
			frappe.throw(_("Select the supplier who will deliver {0} directly.").format(line.item_code))
		if validate_stock:
			_require_dimensions(row, line)

	if validate_stock:
		stock.validate_order_availability(order, warehouse)

	order.run_method("set_missing_values")  # price list rates, UOM, accounts, taxes ...
	_apply_rate_overrides(order, lines)
	if not order.get("taxes") and hasattr(order, "set_taxes"):
		order.set_taxes()
	_apply_discount(order, discount)
	order.calculate_taxes_and_totals()
	return order


def _require_dimensions(row, line: SaleLine) -> None:
	for dimension in dimensions.order_line_dimensions():
		if dimension.required and not row.get(dimension.source):
			frappe.throw(
				_("Select {0} for {1}.").format(_(dimension.label), line.item_code), title=_("Missing Value")
			)


def _apply_rate_overrides(order, lines: list[SaleLine]) -> None:
	"""A rate typed by the cashier replaces the price list rate (ERPNext still applies
	its own selling-price validations on save)."""
	for row, line in zip(order.items, lines, strict=False):
		if line.rate is None or flt(line.rate) == flt(row.rate):
			continue
		row.rate = flt(line.rate)
		row.discount_percentage = 0
		row.discount_amount = flt(row.price_list_rate) - flt(line.rate) if row.price_list_rate else 0
		row.margin_type = None


def _apply_discount(order, discount: Discount | None) -> None:
	"""Transaction discount on the net total (before VAT)."""
	if not discount:
		return
	order.apply_discount_on = "Net Total"
	if discount.kind == "amount":
		order.calculate_taxes_and_totals()
		if discount.value > flt(order.net_total) + 0.01:
			frappe.throw(_("Discount cannot be more than the net total."))
		order.discount_amount = discount.value
		order.additional_discount_percentage = 0
	else:
		order.additional_discount_percentage = discount.value


def totals(doc) -> dict:
	return {
		"subtotal": flt(doc.total),
		"discount": flt(doc.discount_amount),
		"net_total": flt(doc.net_total),
		"taxes": [
			{"description": t.description, "amount": flt(t.tax_amount_after_discount_amount)}
			for t in doc.get("taxes") or []
		],
		"total_taxes": flt(doc.total_taxes_and_charges),
		"grand_total": flt(doc.grand_total),
		"rounded_total": flt(doc.get("rounded_total")) or flt(doc.grand_total),
		"lines": [
			{
				"item_code": d.item_code,
				"rate": flt(d.rate),
				"amount": flt(d.amount),
				"price_list_rate": flt(d.price_list_rate),
			}
			for d in doc.items
		],
	}


def quote(customer: str | None, lines: list[SaleLine], discount: Discount | None) -> dict | None:
	"""Live totals for the cart, calculated by ERPNext exactly as the order will be."""
	if not lines:
		return None
	return totals(build_sales_order(customer, lines, discount, validate_stock=False))
