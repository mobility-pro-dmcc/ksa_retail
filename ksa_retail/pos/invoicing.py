"""Sales Invoices: delivered quantity only, linked the way ERPNext does it.

* delivered, unbilled lines -> invoice made from the Delivery Note (DN <-> SI link);
* supplier-delivered lines  -> invoice made from the Sales Order for the qty the supplier
  delivered (there is no Delivery Note in our books).
Stock never moves through these invoices (Update Stock off) and the advance payments
of the order are allocated before submit.
"""

import frappe
from frappe import _
from frappe.utils import flt, nowdate

from ksa_retail.pos.context import get_context
from ksa_retail.pos.fulfilment import cap_lines, check_open, limit_rows_to

EPSILON = 1e-9


def invoice_order(order_name: str, requested: dict | None = None) -> list[tuple]:
	from erpnext.selling.doctype.sales_order.sales_order import make_sales_invoice as order_to_invoice
	from erpnext.stock.doctype.delivery_note.delivery_note import make_sales_invoice as delivery_to_invoice

	order = frappe.get_doc("Sales Order", order_name)
	check_open(order)
	quantities = cap_lines(order_name, requested, "pending_billing")
	if not quantities:
		frappe.throw(
			_(
				"Nothing delivered to invoice on {0}. Deliver the items first; invoices cover delivered quantity only."
			).format(order_name),
			title=_("Not Delivered"),
		)
	require_address(order.customer)

	created, used = [], {}
	for delivery in _deliveries_pending_billing(order_name):
		invoice = delivery_to_invoice(delivery)
		invoice.items = [r for r in invoice.items if r.get("sales_order") == order_name]
		limit_rows_to(invoice, quantities, used)
		if invoice.items:
			created.append(submit_invoice(invoice))

	supplier_lines = {d.name for d in order.items if d.delivered_by_supplier}
	supplier_quantities = {
		k: v - used.get(k, 0)
		for k, v in quantities.items()
		if k in supplier_lines and v - used.get(k, 0) > EPSILON
	}
	if supplier_quantities:
		invoice = order_to_invoice(order_name)
		invoice.items = [r for r in invoice.items if r.get("so_detail") in supplier_lines]
		limit_rows_to(invoice, supplier_quantities, {})
		if invoice.items:
			created.append(submit_invoice(invoice))

	if not created:
		frappe.throw(_("Nothing selected to invoice."))
	return created


def submit_invoice(invoice) -> tuple:
	invoice.update_stock = 0  # stock moves through Delivery Notes (or the supplier)
	invoice.flags.ksa_pos = True
	invoice.set_posting_time = 0
	invoice.posting_date = nowdate()
	invoice.due_date = None
	invoice.run_method("set_missing_values")
	ensure_sales_taxes(invoice)
	invoice.calculate_taxes_and_totals()
	fill_advances(invoice)
	invoice.insert()
	invoice.submit()
	return ("Sales Invoice", invoice.name)


def ensure_sales_taxes(invoice) -> None:
	"""Orders made before a tax template existed still get VAT on their invoice."""
	if invoice.get("taxes"):
		return
	template = invoice.get("taxes_and_charges") or get_context().tax_template
	if template:
		invoice.taxes_and_charges = template
		invoice.append_taxes_from_master()
	elif invoice.meta.get_field("taxes").reqd:
		frappe.throw(
			_(
				"Sales Invoices need taxes on this site, but there is no default Sales Taxes and Charges "
				"Template for {0}. Create one (e.g. VAT 15%) and tick Default, or set it on your POS Profile."
			).format(invoice.company),
			title=_("Tax Template Missing"),
		)


def fill_advances(invoice, include_unallocated: bool = True) -> None:
	"""Advance Payments table built like ERPNext's "Get Advances", ordered: payments made
	against this invoice's Sales Order(s) first, then the customer's unallocated advances
	(oldest first). Every order-linked payment is listed, so ERPNext's "... should be
	pulled as advance in this invoice" warning never fires."""
	if not invoice.get("debit_to"):
		from erpnext.accounts.party import get_party_account

		invoice.debit_to = get_party_account("Customer", invoice.customer, invoice.company)
	invoice.allocate_advances_automatically = 0  # set here; ERPNext keeps them as-is
	entries = invoice.get_advance_entries(include_unallocated=include_unallocated)
	entries = sorted(entries, key=lambda d: 0 if d.get("against_order") else 1)  # stable: keeps date order

	if invoice.get("party_account_currency") and invoice.party_account_currency != invoice.company_currency:
		total = flt(invoice.get("rounded_total") or invoice.grand_total)
	else:
		total = flt(invoice.get("base_rounded_total") or invoice.base_grand_total)

	invoice.set("advances", [])
	allocated = 0.0
	for entry in entries:
		amount = max(0.0, min(total - allocated, flt(entry.amount)))
		if amount <= 0.005 and not entry.get("against_order"):
			continue
		allocated += amount
		row = {
			"doctype": "Sales Invoice Advance",
			"reference_type": entry.reference_type,
			"reference_name": entry.reference_name,
			"reference_row": entry.reference_row,
			"remarks": entry.remarks,
			"advance_amount": flt(entry.amount),
			"allocated_amount": amount,
			"ref_exchange_rate": flt(entry.exchange_rate),
			"difference_posting_date": invoice.posting_date,
		}
		account = entry.get("paid_to") or entry.get("paid_from")
		if account:
			row["account"] = account
		invoice.append("advances", row)


def require_address(customer: str) -> None:
	field = frappe.get_meta("Sales Invoice").get_field("customer_address")
	if not (field and field.reqd):
		return
	has_address = frappe.db.get_value("Customer", customer, "customer_primary_address") or frappe.db.exists(
		"Dynamic Link", {"link_doctype": "Customer", "link_name": customer, "parenttype": "Address"}
	)
	if not has_address:
		frappe.throw(
			_("Customer {0} has no address. Add one before invoicing (required on Sales Invoice).").format(
				customer
			),
			title=_("Missing Address"),
		)


def _deliveries_pending_billing(order_name: str) -> list[str]:
	return frappe.db.sql_list(
		"""select distinct dn.name from `tabDelivery Note` dn
		join `tabDelivery Note Item` dni on dni.parent = dn.name
		where dn.docstatus = 1 and dn.is_return = 0 and dni.against_sales_order = %s
			and dn.per_billed < 100 and ifnull(dni.against_sales_invoice, '') = ''
		order by dn.creation""",
		order_name,
	)
