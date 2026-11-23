import frappe
from frappe.utils import cint

from ksa_retail.pos import order_summary
from ksa_retail.pos.permissions import pos_endpoint


@frappe.whitelist()
@pos_endpoint
def list_orders(customer: str, only_incomplete: int = 0, start: int = 0, page_length: int = 20):
	frappe.has_permission("Customer", "read", doc=customer, throw=True)
	return order_summary.list_orders(customer, bool(cint(only_incomplete)), start, page_length)


@frappe.whitelist()
@pos_endpoint
def get_order(sales_order: str):
	order = frappe.get_doc("Sales Order", sales_order)
	order.check_permission("read")
	return order_summary.order_detail(order)
