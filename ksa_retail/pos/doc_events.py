"""Document hooks that keep documents created in Desk consistent with the POS rules."""

import frappe
from frappe import _
from frappe.utils import cint, flt

from ksa_retail.pos.invoicing import fill_advances


def sales_invoice_before_validate(doc, method=None):
	"""A new invoice made from a Sales Order pulls the payments made against that order as
	advances. ERPNext checks for missing order advances *before* it would auto-allocate
	them, which is what shows "... should be pulled as advance ..."; filling the table here
	avoids that and allocates the money."""
	if doc.flags.ksa_pos or doc.docstatus != 0 or not doc.is_new():
		return
	if (
		cint(doc.get("is_return"))
		or cint(doc.get("is_pos"))
		or cint(doc.get("allocate_advances_automatically"))
	):
		return
	if not any(d.get("sales_order") for d in doc.get("items") or []):
		return
	try:
		if not doc.get("debit_to"):
			from erpnext.accounts.party import get_party_account

			doc.debit_to = get_party_account("Customer", doc.customer, doc.company)
		have = {a.reference_name for a in doc.get("advances") or []}
		missing = [
			e for e in doc.get_advance_entries(include_unallocated=False) if e.reference_name not in have
		]
		if not missing:
			return
		if not flt(doc.get("grand_total")):
			doc.run_method("set_missing_values")
			doc.calculate_taxes_and_totals()
		fill_advances(doc, include_unallocated=False)
	except Exception:
		# never block saving an invoice because of this convenience; keep the trace
		frappe.log_error(title="KSA POS: pull order advances into Sales Invoice")


def purchase_invoice_before_validate(doc, method=None):
	"""Goods the supplier delivered straight to our customer (drop-ship Purchase Order
	lines) must never be added to our stock by the supplier's invoice."""
	if doc.docstatus != 0 or not cint(doc.get("update_stock")):
		return
	order_lines = [row.po_detail for row in doc.get("items") or [] if row.get("po_detail")]
	if not order_lines or len(order_lines) != len(doc.items):
		return
	supplier_delivered = frappe.get_all(
		"Purchase Order Item", filters={"name": ["in", order_lines], "delivered_by_supplier": 1}, pluck="name"
	)
	if len(supplier_delivered) == len(order_lines):
		doc.update_stock = 0
		frappe.msgprint(
			_(
				"Update Stock was turned off: these items were delivered by the supplier directly to the customer."
			),
			alert=True,
		)
