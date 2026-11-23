"""The POS actions, each one database transaction with one result shape.

Result of every write action:
  {documents: [{doctype, name, action}], order: <order detail> | None,
   customer: <customer summary>, credit_links: [...]}
After the action the customer's unused credit is linked to open invoices (best effort).
"""

import frappe
from frappe import _

from ksa_retail.pos import customers, fulfilment, invoicing, order_editing, payments, pricing, returns
from ksa_retail.pos.inputs import Discount, DropShip, PaymentLine, SaleLine
from ksa_retail.pos.order_summary import order_detail


def create_sale(
	customer: str,
	lines: list[SaleLine],
	discount: Discount | None,
	payments_in: list[PaymentLine],
	deliver: bool,
	drop_ship: DropShip | None,
	client_ref: str,
) -> dict:
	_require_customer(customer)
	existing = frappe.db.get_value("Sales Order", {"ksa_pos_ref": client_ref, "docstatus": 1}, "name")
	if existing:  # retried after the cache expired: never create the sale twice
		return result(customer, existing, [])

	order = pricing.build_sales_order(customer, lines, discount, drop_ship)
	order.ksa_pos_ref = client_ref
	order.insert()
	order.submit()
	created = [("Sales Order", order.name)]
	fulfilment.lock_order(order.name)
	if deliver:
		created += fulfilment.deliver_order(order.name, None, drop_ship.bill_no if drop_ship else None)
	if payments_in:
		created += payments.receive(customer, order.name, payments_in, client_ref)
	return result(customer, order.name, created)


def deliver(
	order_name: str, quantities: dict, bill_no: str | None, payments_in: list[PaymentLine], client_ref: str
) -> dict:
	order = _open_order(order_name)
	created = fulfilment.deliver_order(order.name, quantities, bill_no)
	if payments_in:
		created += payments.receive(order.customer, order.name, payments_in, client_ref)
	return result(order.customer, order.name, created)


def invoice(order_name: str, quantities: dict, payments_in: list[PaymentLine], client_ref: str) -> dict:
	order = _open_order(order_name)
	created = invoicing.invoice_order(order.name, quantities)
	if payments_in:
		created += payments.receive(order.customer, order.name, payments_in, client_ref)
	return result(order.customer, order.name, created)


def pay(customer: str, order_name: str | None, payments_in: list[PaymentLine], client_ref: str) -> dict:
	_require_customer(customer)
	if not payments_in:
		frappe.throw(_("Enter a payment amount."))
	if order_name:
		order = _open_order(order_name, check_open=False)  # money may be taken on any order
		if order.customer != customer:
			frappe.throw(_("Sales Order {0} belongs to another customer.").format(order_name))
	created = payments.receive(customer, order_name, payments_in, client_ref)
	return result(customer, order_name, created)


def update_order(order_name: str, lines: list[SaleLine]) -> dict:
	order = _open_order(order_name, check_open=False)
	created = order_editing.update_order(order.name, lines)
	return result(order.customer, order.name, created, apply_credit=False)


def return_items(order_name: str, quantities: dict, refunds: list[PaymentLine], client_ref: str) -> dict:
	order = _open_order(order_name, check_open=False)
	created = returns.return_items(order.name, quantities, refunds, client_ref)
	return result(order.customer, order.name, created)


def bill_supplier(order_name: str, bill_no: str | None) -> dict:
	order = _open_order(order_name, check_open=False)
	created = fulfilment.bill_supplier_deliveries(order.name, bill_no)
	if not created:
		frappe.throw(_("Nothing delivered by a supplier is waiting for the supplier's invoice."))
	return result(order.customer, order.name, created, apply_credit=False)


def apply_customer_credit(customer: str) -> dict:
	_require_customer(customer)
	frappe.has_permission("Payment Entry", "write", throw=True)
	links = payments.apply_credit(customer)
	if not links:
		frappe.throw(_("No unused payments or credit notes to link with open invoices."))
	return {"links": links, "customer": customers.summary(customer)}


def result(customer: str, order_name: str | None, created: list[tuple], apply_credit: bool = True) -> dict:
	links = payments.apply_credit_safely(customer) if apply_credit else []
	return {
		"documents": [
			{"doctype": doc[0], "name": doc[1], "action": doc[2] if len(doc) > 2 else "created"}
			for doc in created
		],
		"order": order_detail(frappe.get_doc("Sales Order", order_name)) if order_name else None,
		"customer": customers.summary(customer),
		"credit_links": links,
	}


def _require_customer(customer: str | None) -> None:
	if not customer or not frappe.db.exists("Customer", customer):
		frappe.throw(_("Select a customer first."))
	frappe.has_permission("Customer", "read", doc=customer, throw=True)


def _open_order(order_name: str | None, check_open: bool = True):
	if not order_name or not frappe.db.exists("Sales Order", order_name):
		frappe.throw(_("Sales Order {0} not found.").format(order_name or ""), frappe.DoesNotExistError)
	fulfilment.lock_order(order_name)
	order = frappe.get_doc("Sales Order", order_name)
	order.check_permission("read")
	if check_open:
		fulfilment.check_open(order)
	return order
