"""Data embedded in the POS page on load (one round trip less on start-up)."""

import frappe
from frappe import _
from frappe.utils import cstr, nowdate

from ksa_retail.pos import dimensions
from ksa_retail.pos.context import get_context, permitted_warehouses
from ksa_retail.pos.fulfilment import bill_no_required

PREFERENCE_KEYS = ("mode_of_payment", "lang", "theme", "warehouse")
PREFERENCE_VALUES = {"lang": ("en", "ar"), "theme": ("", "light", "dark")}
PRINTABLE_DOCTYPES = (
	"Sales Order", "Delivery Note", "Sales Invoice", "Payment Entry", "Purchase Order", "Purchase Invoice",
)  # fmt: skip
PERMISSION_DOCTYPES = ("Customer", *PRINTABLE_DOCTYPES)


def get_boot() -> dict:
	context = get_context()
	user = frappe.get_cached_doc("User", frappe.session.user)
	return {
		"settings": {
			"company": context.company,
			"currency": context.currency,
			"warehouse": context.warehouse,
			"warehouses": context.warehouses,
			"price_list": context.price_list,
			"payment_modes": context.payment_modes,
		},
		"logo": _logo(context.company),
		"dimensions": [
			{
				"fieldname": d.source,
				"label": d.label,
				"label_ar": _(d.label, lang="ar"),
				"doctype": d.reference_doctype,
				"required": d.required,
			}
			for d in dimensions.get_dimensions()
		],
		"user": {
			"name": user.name,
			"full_name": user.full_name,
			"image": user.user_image,
			"initials": "".join(w[0] for w in cstr(user.full_name or user.name).split()[:2]).upper(),
		},
		"prefs": {k: frappe.defaults.get_user_default(f"ksa_pos_{k}") for k in PREFERENCE_KEYS},
		"desk_url": "/desk" if _major_version("frappe") >= 16 else "/app",
		"bill_no_required": bill_no_required(),
		"print_formats": {
			dt: frappe.get_meta(dt).default_print_format or "Standard" for dt in PRINTABLE_DOCTYPES
		},
		"perms": {
			dt: {p: bool(frappe.has_permission(dt, p)) for p in ("create", "submit")}
			for dt in PERMISSION_DOCTYPES
		},
		"today": nowdate(),
	}


def set_preference(key: str, value) -> None:
	value = cstr(value)
	if key not in PREFERENCE_KEYS:
		frappe.throw(_("Unknown preference"))
	if key in PREFERENCE_VALUES and value not in PREFERENCE_VALUES[key]:
		frappe.throw(_("Invalid value for {0}").format(key))
	if key == "mode_of_payment" and value and not frappe.db.exists("Mode of Payment", value):
		frappe.throw(_("Mode of Payment {0} does not exist").format(value))
	if key == "warehouse" and value not in permitted_warehouses(get_context().company):
		frappe.throw(
			_("You are not permitted to sell from warehouse {0}.").format(value), frappe.PermissionError
		)
	frappe.defaults.set_user_default(f"ksa_pos_{key}", value)


def _logo(company: str) -> str | None:
	return (
		frappe.get_cached_value("Company", company, "company_logo")
		or frappe.db.get_single_value("Navbar Settings", "app_logo")
		or frappe.db.get_single_value("Website Settings", "app_logo")
	)


def _major_version(app: str) -> int:
	try:
		return int(cstr(frappe.get_attr(f"{app}.__version__")).split(".")[0])
	except Exception:
		return 0
