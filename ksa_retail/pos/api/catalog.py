import frappe

from ksa_retail.pos import catalog, dimensions, inputs, pricing
from ksa_retail.pos.permissions import pos_endpoint


@frappe.whitelist()
@pos_endpoint
def search_items(
	query: str = "", brand: str | None = None, start: int = 0, page_length: int = 24, in_stock: int = 0
):
	return catalog.search_items(query, brand, start, page_length, in_stock)


@frappe.whitelist()
@pos_endpoint
def get_dimension_values(fieldname: str):
	return dimensions.allowed_values(fieldname)


@frappe.whitelist()
@pos_endpoint
def search_suppliers(query: str = ""):
	return catalog.search_suppliers(query)


@frappe.whitelist(methods=["POST"])
@pos_endpoint
def quote_sale(customer: str | None = None, lines=None, discount=None):
	"""Totals of the cart as ERPNext will calculate them (nothing is saved)."""
	return pricing.quote(
		customer,
		inputs.sale_lines(lines, dimensions.source_fields()),
		inputs.discount(discount),
	)
