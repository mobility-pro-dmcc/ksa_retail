"""Write actions. Each runs once per `client_ref` (see ksa_retail.pos.idempotency)."""

import frappe
from frappe.utils import cint

from ksa_retail.pos import dimensions, inputs, transactions
from ksa_retail.pos.idempotency import run_once
from ksa_retail.pos.permissions import pos_endpoint


@frappe.whitelist(methods=["POST"])
@pos_endpoint
def create_sale(
	client_ref: str, customer: str, lines, discount=None, payments=None, deliver: int = 0, drop_ship=None
):
	"""New Sales Order from the cart; optionally delivered at once and/or paid."""
	ref = inputs.client_ref(client_ref)
	sale_lines = inputs.sale_lines(lines, dimensions.source_fields())
	return run_once(
		ref,
		lambda: transactions.create_sale(
			customer,
			sale_lines,
			inputs.discount(discount),
			inputs.payment_lines(payments),
			bool(cint(deliver)),
			inputs.drop_ship(drop_ship),
			ref,
		),
	)


@frappe.whitelist(methods=["POST"])
@pos_endpoint
def deliver_order(
	client_ref: str, sales_order: str, quantities=None, bill_no: str | None = None, payments=None
):
	ref = inputs.client_ref(client_ref)
	return run_once(
		ref,
		lambda: transactions.deliver(
			sales_order,
			inputs.line_quantities(quantities),
			inputs.text(bill_no, "Bill No"),
			inputs.payment_lines(payments),
			ref,
		),
	)


@frappe.whitelist(methods=["POST"])
@pos_endpoint
def invoice_order(client_ref: str, sales_order: str, quantities=None, payments=None):
	ref = inputs.client_ref(client_ref)
	return run_once(
		ref,
		lambda: transactions.invoice(
			sales_order, inputs.line_quantities(quantities), inputs.payment_lines(payments), ref
		),
	)


@frappe.whitelist(methods=["POST"])
@pos_endpoint
def register_payment(client_ref: str, customer: str, payments, sales_order: str | None = None):
	ref = inputs.client_ref(client_ref)
	return run_once(
		ref, lambda: transactions.pay(customer, sales_order or None, inputs.payment_lines(payments), ref)
	)


@frappe.whitelist(methods=["POST"])
@pos_endpoint
def update_order(client_ref: str, sales_order: str, lines):
	ref = inputs.client_ref(client_ref)
	sale_lines = inputs.sale_lines(lines, dimensions.source_fields())
	return run_once(ref, lambda: transactions.update_order(sales_order, sale_lines))


@frappe.whitelist(methods=["POST"])
@pos_endpoint
def return_items(client_ref: str, sales_order: str, quantities, refunds=None):
	ref = inputs.client_ref(client_ref)
	return run_once(
		ref,
		lambda: transactions.return_items(
			sales_order, inputs.line_quantities(quantities), inputs.payment_lines(refunds), ref
		),
	)


@frappe.whitelist(methods=["POST"])
@pos_endpoint
def bill_supplier(client_ref: str, sales_order: str, bill_no: str | None = None):
	ref = inputs.client_ref(client_ref)
	return run_once(ref, lambda: transactions.bill_supplier(sales_order, inputs.text(bill_no, "Bill No")))
