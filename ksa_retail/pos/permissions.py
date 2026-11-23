"""Authorization boundary for the POS endpoints.

The POS never elevates privileges: documents are created as the current user, so
ERPNext's own permission checks on insert/submit still apply. These helpers add the
POS-level gate and clear messages for the checks the POS performs up front.
"""

import functools

import frappe
from frappe import _


def has_app_permission() -> bool:
	"""Who may open the POS: anyone allowed to create Sales Orders."""
	return bool(frappe.has_permission("Sales Order", "create"))


def require_pos_access() -> None:
	if frappe.session.user == "Guest" or not has_app_permission():
		frappe.throw(_("You are not permitted to use the POS."), frappe.PermissionError)


def require(doctype: str, ptype: str, doc=None) -> None:
	frappe.has_permission(doctype, ptype, doc=doc, throw=True)


def apply_pos_language() -> None:
	"""Server messages in the language the cashier chose in the POS."""
	lang = frappe.defaults.get_user_default("ksa_pos_lang")
	if lang in ("ar", "en"):
		frappe.local.lang = lang


def pos_endpoint(fn):
	"""Decorator for every whitelisted POS method: access gate + POS language."""

	@functools.wraps(fn)
	def wrapper(*args, **kwargs):
		require_pos_access()
		apply_pos_language()
		return fn(*args, **kwargs)

	return wrapper
