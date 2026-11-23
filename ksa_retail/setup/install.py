"""Schema setup for the KSA Retail POS.

Runs after install and after every migrate, so it is idempotent.

1. Inventory Dimensions (e.g. "Production Year") are only added by ERPNext to
   stock transactions. The POS records the chosen dimension value on the
   Sales Order line so it flows to the Delivery Note / Sales Invoice through
   the standard mappers (same fieldname => copied by get_mapped_doc).
2. A hidden `ksa_pos_ref` field on Sales Order and Payment Entry stores the
   client transaction id, used to block duplicate submissions.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def after_migrate(*args, **kwargs):
	if "erpnext" not in frappe.get_installed_apps():
		return

	fields = {
		"Sales Order": [_pos_ref_field("customer")],
		"Payment Entry": [_pos_ref_field("party")],
	}

	so_item_fields = []
	for dim in get_inventory_dimensions():
		if frappe.get_meta("Sales Order Item").has_field(dim.source_fieldname):
			continue
		so_item_fields.append(
			{
				"fieldname": dim.source_fieldname,
				"label": dim.dimension_name,
				"fieldtype": "Link",
				"options": dim.reference_document,
				"insert_after": "warehouse",
				"in_list_view": 0,
				"allow_on_submit": 0,
				"search_index": 1,
				"module": "Ksa Retail",
			}
		)
	if so_item_fields:
		fields["Sales Order Item"] = so_item_fields

	create_custom_fields(fields, ignore_validate=True, update=True)


def _pos_ref_field(insert_after):
	return {
		"fieldname": "ksa_pos_ref",
		"label": "POS Transaction Ref",
		"fieldtype": "Data",
		"insert_after": insert_after,
		"hidden": 1,
		"read_only": 1,
		"no_copy": 1,
		"print_hide": 1,
		"report_hide": 1,
		"search_index": 1,
		"module": "Ksa Retail",
	}


def get_inventory_dimensions():
	"""Inventory Dimensions that apply to Delivery Notes (selling stock out)."""
	if not frappe.db.exists("DocType", "Inventory Dimension"):
		return []

	meta = frappe.get_meta("Inventory Dimension")
	fields = ["name", "dimension_name", "reference_document", "source_fieldname", "target_fieldname"]
	for optional in ("apply_to_all_doctypes", "document_type", "disabled", "reqd"):
		if meta.has_field(optional):
			fields.append(optional)

	dims = []
	for d in frappe.get_all("Inventory Dimension", fields=fields, order_by="creation asc"):
		if d.get("disabled"):
			continue
		if not (d.get("apply_to_all_doctypes") or d.get("document_type") == "Delivery Note"):
			continue
		if not d.source_fieldname or not d.target_fieldname:
			continue
		dims.append(d)
	return dims
