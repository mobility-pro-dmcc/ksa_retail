import frappe

from ksa_retail.pos import customers, transactions
from ksa_retail.pos.inputs import parse_json
from ksa_retail.pos.permissions import pos_endpoint


@frappe.whitelist()
@pos_endpoint
def search_customers(query: str = "", limit: int = 20):
	return customers.search(query, limit)


@frappe.whitelist()
@pos_endpoint
def get_customer(customer: str):
	return customers.summary(customer)


@frappe.whitelist()
@pos_endpoint
def get_registration_form():
	return customers.registration_form()


@frappe.whitelist(methods=["POST"])
@pos_endpoint
def register_customer(values):
	return customers.register(parse_json(values, expected=dict, default={}))


@frappe.whitelist(methods=["POST"])
@pos_endpoint
def apply_customer_credit(customer: str):
	return transactions.apply_customer_credit(customer)
