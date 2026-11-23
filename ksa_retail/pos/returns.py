"""Returns with ERPNext's standard return documents.

* delivered qty -> return Delivery Note (make_sales_return on the original delivery);
  stock comes back with the same batch and dimension values;
* invoiced qty  -> credit note made **from the return Delivery Note** (linked to it, to
  the order and to the original invoice via Return Against); invoiced-but-never-delivered
  qty gets a credit note against the invoice;
* the credit note reduces the invoice when that is still unpaid, otherwise it stays as
  refundable customer credit; optional refunds are paid against the new credit notes.
"""

import frappe
from frappe import _
from frappe.utils import flt, nowdate

from ksa_retail.pos import order_summary, payments
from ksa_retail.pos.context import get_context
from ksa_retail.pos.inputs import PaymentLine

EPSILON = 1e-9


def return_items(
	order_name: str, quantities: dict, refunds: list[PaymentLine], client_ref: str
) -> list[tuple]:
	order = frappe.get_doc("Sales Order", order_name)
	if not quantities:
		frappe.throw(_("Select the quantities to return."))

	progress = order_summary.line_progress([order_name])
	rows = {d.name: d for d in order.items}
	for line, qty in quantities.items():
		if line not in rows:
			frappe.throw(_("Line {0} is not on {1}.").format(line, order_name))
		allowed = progress[line].returnable
		if qty > allowed + 1e-6:
			frappe.throw(
				_("Row {0} ({1}): you can return at most {2}.").format(
					rows[line].idx, rows[line].item_code, allowed
				)
			)

	created: list[tuple] = []
	stock_quantities = {
		line: min(qty, progress[line].net_dn)
		for line, qty in quantities.items()
		if not rows[line].delivered_by_supplier and progress[line].net_dn > 0
	}
	return_deliveries = []
	if stock_quantities:
		frappe.has_permission("Delivery Note", "submit", throw=True)
		return_deliveries = _return_deliveries(order_name, stock_quantities)
		created += [("Delivery Note", name) for name in return_deliveries]

	money_quantities = {
		line: min(qty, progress[line].net_si) for line, qty in quantities.items() if progress[line].net_si > 0
	}
	credit_notes: list[str] = []
	if money_quantities:
		frappe.has_permission("Sales Invoice", "submit", throw=True)
		for delivery in return_deliveries:
			credit_notes += _credit_note_from_return_delivery(delivery, money_quantities)
		left = {k: v for k, v in money_quantities.items() if v > EPSILON}
		if left:  # invoiced but never delivered
			credit_notes += _credit_notes_from_invoices(order_name, left)
		created += [("Sales Invoice", name) for name in credit_notes]

	if refunds:
		created += payments.refund(order.customer, credit_notes, refunds, client_ref)

	order.add_comment("Info", _("Return from KSA Retail POS: {0}").format(", ".join(n for _dt, n in created)))
	return created


def _trim_return_rows(doc, wanted: dict) -> bool:
	"""Keep only the rows / quantities being returned (negative qty). Returns True if any left."""
	keep = []
	for row in doc.items:
		want = wanted.get(row.get("so_detail"), 0)
		if want <= EPSILON or abs(flt(row.qty)) <= EPSILON:
			continue
		qty = min(want, abs(flt(row.qty)))
		row.qty = -qty
		row.stock_qty = -qty * flt(row.conversion_factor or 1)
		wanted[row.so_detail] = want - qty
		keep.append(row)
	doc.set("items", keep)
	for idx, row in enumerate(doc.items, 1):
		row.idx = idx
	return bool(keep)


def _return_deliveries(order_name: str, quantities: dict) -> list[str]:
	from erpnext.stock.doctype.delivery_note.delivery_note import make_sales_return

	left = dict(quantities)
	created = []
	deliveries = frappe.db.sql_list(
		"""select distinct dn.name from `tabDelivery Note` dn
		join `tabDelivery Note Item` dni on dni.parent = dn.name
		where dn.docstatus = 1 and dn.is_return = 0 and dni.against_sales_order = %s and dni.so_detail in %s
		order by dn.posting_date desc, dn.creation desc""",
		(order_name, tuple(quantities)),
	)
	for delivery in deliveries:
		if all(v <= EPSILON for v in left.values()):
			break
		returned = make_sales_return(delivery)
		if not _trim_return_rows(returned, left):
			continue
		returned.insert()
		returned.submit()
		created.append(returned.name)
	return created


def _original_invoice_row(return_row) -> tuple | None:
	"""(invoice, invoice row) that billed the delivery this return row reverses."""
	original_delivery_row = return_row.get("dn_detail")
	if not original_delivery_row:
		return None
	row = frappe.db.sql(
		"""select sii.parent, sii.name from `tabSales Invoice Item` sii
		join `tabSales Invoice` si on si.name = sii.parent
		where si.docstatus = 1 and si.is_return = 0 and sii.dn_detail = %s
		order by si.creation limit 1""",
		original_delivery_row,
	)
	if row:
		return row[0]
	# delivery made from the invoice (invoiced first)
	return (
		frappe.db.get_value(
			"Delivery Note Item", original_delivery_row, ["against_sales_invoice", "si_detail"]
		)
		or None
	)


def _prepare_credit_note(credit_note) -> None:
	credit_note.update_stock = 0  # stock comes back through the return Delivery Note
	credit_note.set("payments", [])
	credit_note.set("advances", [])
	credit_note.allocate_advances_automatically = 0
	credit_note.is_pos = 0
	credit_note.flags.ksa_pos = True


def _settle_mode(credit_note, invoice: str | None) -> None:
	"""Unpaid invoice: reduce what the customer owes; paid invoice: keep as refundable credit."""
	if not credit_note.meta.has_field("update_outstanding_for_self"):
		return
	outstanding = flt(frappe.db.get_value("Sales Invoice", invoice, "outstanding_amount")) if invoice else 0
	total = abs(flt(credit_note.rounded_total or credit_note.grand_total))
	credit_note.update_outstanding_for_self = 0 if invoice and outstanding >= total - 0.01 else 1


def _credit_note_from_return_delivery(return_delivery: str, money_quantities: dict) -> list[str]:
	from erpnext.stock.doctype.delivery_note.delivery_note import make_sales_invoice

	try:
		credit_note = make_sales_invoice(return_delivery)
	except frappe.ValidationError:
		frappe.clear_last_message()
		return []  # nothing on this return to credit
	return_rows = {d.name: d for d in frappe.get_doc("Delivery Note", return_delivery).items}
	keep, invoices = [], set()
	for row in credit_note.items:
		want = money_quantities.get(row.get("so_detail"), 0)
		original = _original_invoice_row(return_rows.get(row.get("dn_detail")) or {})
		if want <= EPSILON or not original or not original[0]:
			continue  # never invoiced: the stock return is enough
		qty = min(want, abs(flt(row.qty)))
		row.qty = -qty
		row.stock_qty = -qty * flt(row.conversion_factor or 1)
		if row.meta.has_field("sales_invoice_item"):
			row.sales_invoice_item = original[1]
		money_quantities[row.so_detail] = want - qty
		invoices.add(original[0])
		keep.append(row)
	if not keep:
		return []
	credit_note.set("items", keep)
	for idx, row in enumerate(credit_note.items, 1):
		row.idx = idx
	credit_note.is_return = 1
	if len(invoices) == 1:
		credit_note.return_against = next(iter(invoices))
	_prepare_credit_note(credit_note)
	credit_note.set_posting_time = 0
	credit_note.posting_date = nowdate()
	tax_template = credit_note.get("taxes_and_charges") or get_context().tax_template
	if not credit_note.get("taxes") and tax_template:
		credit_note.taxes_and_charges = tax_template
		credit_note.append_taxes_from_master()
	credit_note.calculate_taxes_and_totals()
	_settle_mode(credit_note, credit_note.get("return_against"))
	credit_note.insert()
	credit_note.submit()
	return [credit_note.name]


def _credit_notes_from_invoices(order_name: str, quantities: dict) -> list[str]:
	from erpnext.accounts.doctype.sales_invoice.sales_invoice import make_sales_return

	left = dict(quantities)
	created = []
	invoices = frappe.db.sql(
		"""select distinct si.name, si.outstanding_amount from `tabSales Invoice` si
		join `tabSales Invoice Item` sii on sii.parent = si.name
		where si.docstatus = 1 and si.is_return = 0 and sii.sales_order = %s and sii.so_detail in %s
		order by si.posting_date desc, si.creation desc""",
		(order_name, tuple(quantities)),
		as_dict=True,
	)
	for invoice in invoices:
		if all(v <= EPSILON for v in left.values()):
			break
		credit_note = make_sales_return(invoice.name)
		if not _trim_return_rows(credit_note, left):
			continue
		_prepare_credit_note(credit_note)
		credit_note.calculate_taxes_and_totals()
		_settle_mode(credit_note, invoice.name)
		credit_note.insert()
		credit_note.submit()
		created.append(credit_note.name)
	return created
