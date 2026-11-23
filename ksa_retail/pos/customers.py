"""Customers in the POS: search, account summary, registration."""

import frappe
from frappe import _
from frappe.utils import cint, cstr, flt

from ksa_retail.pos.context import get_context

SEARCH_LIMIT = 20
MAX_SEARCH_LIMIT = 50
LINK_CHOICES_LIMIT = 300
SKIPPED_FORM_FIELD_TYPES = {
	"Section Break", "Column Break", "Tab Break", "Table", "Table MultiSelect", "HTML", "Button",
	"Image", "Attach", "Attach Image", "Fold", "Heading", "Signature", "Geolocation", "Text Editor",
	"Code", "HTML Editor", "Markdown Editor", "JSON", "Read Only",
}  # fmt: skip
# Fields ERPNext's Customer quick entry understands: it creates the primary contact / address
QUICK_ENTRY_FIELDS = [
	{"fieldname": "mobile_no", "label": "Mobile No", "fieldtype": "Data", "options": "Phone"},
	{"fieldname": "email_id", "label": "Email Id", "fieldtype": "Data", "options": "Email"},
	{"fieldname": "address_line1", "label": "Address Line 1", "fieldtype": "Data"},
	{"fieldname": "city", "label": "City/Town", "fieldtype": "Data"},
	{"fieldname": "country", "label": "Country", "fieldtype": "Link", "options": "Country"},
]


def search(query: str = "", limit: int = SEARCH_LIMIT) -> list[dict]:
	"""By name / code / mobile plus the Customer DocType's configured search fields."""
	meta = frappe.get_meta("Customer")
	query = cstr(query).strip()
	or_filters = None
	if query:
		fields = {"name", "customer_name", "mobile_no"}
		fields |= {f.strip() for f in cstr(meta.search_fields).split(",") if f.strip()}
		or_filters = [
			[f, "like", f"%{query.replace(' ', '') if f == 'mobile_no' else query}%"]
			for f in sorted(fields)
			if f == "name" or meta.has_field(f)
		]
	return frappe.get_list(
		"Customer",
		fields=["name", "customer_name", "mobile_no", "territory", "customer_group", "image"],
		filters={"disabled": 0},
		or_filters=or_filters,
		order_by="modified desc",
		limit_page_length=min(cint(limit) or SEARCH_LIMIT, MAX_SEARCH_LIMIT),
	)


def summary(customer: str) -> dict:
	"""Card data: contact, address presence and the customer's money position."""
	if not frappe.db.exists("Customer", customer):
		frappe.throw(_("Customer {0} not found.").format(customer), frappe.DoesNotExistError)
	frappe.has_permission("Customer", "read", doc=customer, throw=True)
	company = get_context().company
	row = frappe.db.get_value(
		"Customer",
		customer,
		[
			"name",
			"customer_name",
			"mobile_no",
			"territory",
			"customer_group",
			"image",
			"customer_primary_address",
		],
		as_dict=True,
	)

	from erpnext.accounts.utils import get_balance_on

	open_invoices, credit_notes = frappe.db.sql(
		"""select
			sum(case when outstanding_amount > 0 then outstanding_amount else 0 end),
			sum(case when outstanding_amount < 0 then -outstanding_amount else 0 end)
		from `tabSales Invoice` where docstatus = 1 and customer = %s and company = %s""",
		(customer, company),
	)[0]
	unallocated = frappe.db.sql(
		"""select sum(unallocated_amount) from `tabPayment Entry`
		where docstatus = 1 and party_type = 'Customer' and party = %s
			and company = %s and payment_type = 'Receive'""",
		(customer, company),
	)[0][0]
	has_address = bool(row.customer_primary_address) or bool(
		frappe.db.exists(
			"Dynamic Link", {"link_doctype": "Customer", "link_name": customer, "parenttype": "Address"}
		)
	)
	return {
		"name": row.name,
		"customer_name": row.customer_name,
		"mobile_no": row.mobile_no,
		"territory": row.territory,
		"customer_group": row.customer_group,
		"image": row.image,
		"has_address": has_address,
		"balance": flt(get_balance_on(party_type="Customer", party=customer, company=company)),
		"open_invoices": flt(open_invoices),
		# money the customer can still use: free payments + credit notes not refunded / applied
		"advance": flt(unallocated) + flt(credit_notes),
	}


def registration_form() -> list[dict]:
	"""Driven by the Customer DocType: mandatory fields, fields marked In Preview / Allow in
	Quick Entry, plus the contact & address fields ERPNext's quick entry uses."""
	frappe.has_permission("Customer", "create", throw=True)
	meta = frappe.get_meta("Customer")
	selling = frappe.get_cached_doc("Selling Settings")
	defaults = {
		"customer_group": selling.get("customer_group"),
		"territory": selling.get("territory"),
		"country": frappe.db.get_single_value("System Settings", "country"),
	}
	fields = [
		_form_field(df, defaults)
		for df in meta.fields
		if df.fieldtype not in SKIPPED_FORM_FIELD_TYPES
		and df.fieldname != "naming_series"
		and not df.hidden
		and not df.read_only
		and (df.reqd or df.in_preview or df.allow_in_quick_entry)
	]
	present = {f["fieldname"] for f in fields}
	fields += [
		_form_field(frappe._dict(f), defaults) for f in QUICK_ENTRY_FIELDS if f["fieldname"] not in present
	]
	return fields


def register(values: dict) -> dict:
	allowed = {f["fieldname"] for f in registration_form()}
	clean = {k: v for k, v in (values or {}).items() if k in allowed and v not in (None, "")}
	if clean.get("mobile_no"):
		clean["mobile_no"] = cstr(clean["mobile_no"]).replace(" ", "")
	if clean.get("address_line1") and not clean.get("city"):
		frappe.throw(_("City is required when an address is entered."))
	doc = frappe.get_doc({"doctype": "Customer", **clean})
	doc.insert()
	return summary(doc.name)


def _form_field(df, defaults: dict) -> dict:
	field = {
		"fieldname": df.fieldname,
		"fieldtype": df.fieldtype,
		"label": {"en": df.label, "ar": _(df.label, lang="ar")},
		"reqd": cint(df.reqd),
		"options": df.options,
		"default": defaults.get(df.fieldname) or df.default,
	}
	if df.fieldtype == "Select":
		field["choices"] = [o for o in cstr(df.options).split("\n") if o]
	elif df.fieldtype == "Link" and df.options:
		link_meta = frappe.get_meta(df.options)
		filters = {"is_group": 0} if link_meta.has_field("is_group") else {}
		if link_meta.has_field("disabled"):
			filters["disabled"] = 0
		field["choices"] = frappe.get_list(
			df.options,
			filters=filters,
			pluck="name",
			limit_page_length=LINK_CHOICES_LIMIT,
			order_by="name asc",
		)
	return field
