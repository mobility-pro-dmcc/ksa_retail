"""The selling context of the current user.

Resolved once per request, in this order: the user's POS Profile (ERPNext standard),
then user defaults, then Global / Stock / Selling defaults.

Settings fields differ between ERPNext versions (v16 dropped Stock Settings
`default_warehouse`), so settings are read through `_setting`, which treats a
missing field as "not set" instead of failing.
"""

import frappe
from frappe import _
from frappe.utils import cint

_CACHE_ATTR = "ksa_pos_context"


def get_context() -> frappe._dict:
	cache = getattr(frappe.local, _CACHE_ATTR, None) or {}
	user = frappe.session.user
	if user not in cache:
		cache[user] = _resolve(user)
		setattr(frappe.local, _CACHE_ATTR, cache)
	return cache[user]


def clear_cache() -> None:
	if hasattr(frappe.local, _CACHE_ATTR):
		delattr(frappe.local, _CACHE_ATTR)


def payment_mode(name: str) -> dict:
	mode = next((m for m in get_context().payment_modes if m["name"] == name), None)
	if not mode:
		frappe.throw(
			_("Mode of Payment {0} is not allowed or has no account for {1}.").format(
				name, get_context().company
			)
		)
	return mode


def require_warehouse() -> str:
	warehouse = get_context().warehouse
	if not warehouse:
		frappe.throw(_("No warehouse is available to you. Set one in your POS Profile or user defaults, or ask for warehouse permission."))
	return warehouse


def _resolve(user: str) -> frappe._dict:
	profile = _pos_profile(user)
	company = _company(profile)
	warehouses = permitted_warehouses(company)
	return frappe._dict(
		company=company,
		currency=frappe.get_cached_value("Company", company, "default_currency"),
		warehouse=_warehouse(profile, warehouses),
		warehouses=warehouses,
		price_list=(profile and profile.selling_price_list)
		or _setting("Selling Settings", "selling_price_list"),
		tax_template=(profile and profile.taxes_and_charges)
		or frappe.db.get_value(
			"Sales Taxes and Charges Template", {"company": company, "is_default": 1, "disabled": 0}, "name"
		),
		pos_profile=profile and profile.name,
		payment_modes=_payment_modes(company, profile),
	)


def _setting(doctype: str, fieldname: str):
	"""A Single DocType value, or None when this version has no such field."""
	if not frappe.get_meta(doctype).has_field(fieldname):
		return None
	return frappe.db.get_single_value(doctype, fieldname)


def _pos_profile(user: str):
	if not frappe.db.exists("DocType", "POS Profile"):
		return None
	name = frappe.db.sql(
		"""select p.name from `tabPOS Profile` p
		join `tabPOS Profile User` u on u.parent = p.name
		where u.user = %s and p.disabled = 0
		order by u.`default` desc, p.modified desc limit 1""",
		user,
	)
	return frappe.get_cached_doc("POS Profile", name[0][0]) if name else None


def _company(profile) -> str:
	company = (
		(profile and profile.company)
		or frappe.defaults.get_user_default("Company")
		or _setting("Global Defaults", "default_company")
	)
	if not company:
		companies = frappe.get_list("Company", pluck="name", limit_page_length=1)
		company = companies[0] if companies else None
	if not company:
		frappe.throw(_("No company is set up."))
	return company


def permitted_warehouses(company: str) -> list[str]:
	"""Stock warehouses of the company this user may use. `get_list` applies the user's
	permissions, so User Permissions on Warehouse narrow the list; no restriction = all."""
	return frappe.get_list(
		"Warehouse",
		filters={"company": company, "is_group": 0, "disabled": 0},
		pluck="name",
		order_by="name asc",
		limit_page_length=0,
	)


def _warehouse(profile, permitted: list[str]) -> str | None:
	"""The cashier's own choice in the POS first, then the usual ERPNext defaults; always one
	of the permitted warehouses."""
	allowed = set(permitted)
	candidates = [
		frappe.defaults.get_user_default("ksa_pos_warehouse"),
		profile and profile.warehouse,
		frappe.defaults.get_user_default("Warehouse"),
		_setting("Stock Settings", "default_warehouse"),  # gone in v16
	]
	for warehouse in candidates:
		if warehouse in allowed:
			return warehouse
	return permitted[0] if permitted else None


def _payment_modes(company: str, profile) -> list[dict]:
	"""Enabled modes of payment that have an account for this company (one query)."""
	profile_modes = {p.mode_of_payment: cint(p.default) for p in (profile.get("payments") if profile else [])}
	rows = frappe.db.sql(
		"""select mpa.parent as name, mp.type, mpa.default_account as account, acc.account_type
		from `tabMode of Payment Account` mpa
		join `tabMode of Payment` mp on mp.name = mpa.parent
		left join `tabAccount` acc on acc.name = mpa.default_account
		where mpa.company = %s and mp.enabled = 1 and ifnull(mpa.default_account, '') != ''
		order by mp.name""",
		company,
		as_dict=True,
	)
	if profile_modes:
		order = list(profile_modes)
		rows = sorted((r for r in rows if r.name in profile_modes), key=lambda r: order.index(r.name))

	modes = [
		{
			"name": r.name,
			"type": r.type,
			"account": r.account,
			"requires_reference": r.account_type == "Bank",
		}
		for r in rows
	]
	default = _default_mode(modes, profile_modes)
	modes.sort(key=lambda m: m["name"] != default)
	for mode in modes:
		mode["is_default"] = mode["name"] == default
	return modes


def _default_mode(modes: list[dict], profile_modes: dict) -> str | None:
	names = [m["name"] for m in modes]
	preferred = frappe.defaults.get_user_default("ksa_pos_mode_of_payment")
	if preferred in names:
		return preferred
	for candidate in (
		next((n for n in names if profile_modes.get(n)), None),
		next((m["name"] for m in modes if m["type"] == "Cash"), None),
	):
		if candidate:
			return candidate
	return names[0] if names else None
