import frappe

from ksa_retail.pos import boot
from ksa_retail.pos.permissions import pos_endpoint


@frappe.whitelist(methods=["POST"])
@pos_endpoint
def set_preference(key: str, value: str | None = None):
	boot.set_preference(key, value)
	return True
