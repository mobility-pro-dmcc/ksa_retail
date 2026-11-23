"""Demo data for presenting the KSA Retail POS.

    bench --site <site> execute ksa_retail.demo.create
    bench --site <site> execute ksa_retail.demo.remove

Everything created is recorded in <site>/private/files/ksa_pos_demo.json, and `remove`
cancels / deletes exactly those records (newest first). Orders are created through the
POS API itself, so the demo exercises the same flows a cashier uses.
"""

import json
import os
import uuid

import frappe
from frappe.utils import flt, nowdate

from ksa_retail.pos.api import sales
from ksa_retail.pos.context import get_context

LOG_FILE = "ksa_pos_demo.json"

BRANDS = [
	("Michelin", "MI", "France"),
	("Bridgestone", "BS", "Japan"),
	("Pirelli", "PI", "Italy"),
	("Continental", "CO", "Germany"),
	("Hankook", "HK", "South Korea"),
	("Yokohama", "YO", "Japan"),
]

# code, brand, size, ply, pattern, price, buying, {year: qty}
ITEMS = [
	(
		"DEMO-T001",
		"Michelin",
		"205/55R16",
		"P04",
		"PRIMACY 4",
		465,
		330,
		{"2024": 15, "2025": 30, "2026": 20},
	),
	("DEMO-T002", "Bridgestone", "215/60R16", "P04", "TURANZA T005", 410, 290, {"2025": 24, "2026": 12}),
	("DEMO-T003", "Pirelli", "265/65R17", "P06", "SCORPION VERDE", 690, 510, {"2024": 4, "2025": 18}),
	("DEMO-T004", "Continental", "265/70R16", "P08", "CROSSCONTACT LX2", 615, 450, {"2024": 8, "2026": 14}),
	("DEMO-T005", "Hankook", "225/45R18", "P04", "VENTUS PRIME4", 520, 380, {"2026": 40}),
	("DEMO-T006", "Yokohama", "245/70R16", "P08", "GEOLANDAR AT G015", 575, 420, {"2025": 22}),
	("DEMO-T007", "Michelin", "195/65R15", "P04", "ENERGY XM2+", 330, 235, {"2024": 36, "2025": 50}),
	("DEMO-T008", "Pirelli", "285/50R20", "P06", "SCORPION ZERO", 980, 760, {}),  # supplier-delivered only
]

CUSTOMERS = [
	("مؤسسة الحربي لقطع الغيار", "Company", "Commercial", "Riyadh", "0551284903", "طريق الملك فهد", "Riyadh"),
	("Faisal Al-Otaibi", "Individual", "Individual", "Riyadh", "0503771260", "Olaya St 12", "Riyadh"),
	("شركة النخبة للنقل", "Company", "Commercial", "Dammam", "0548092117", "حي الفيصلية", "Dammam"),
	("Al Waha Car Care", "Company", "Commercial", "Jeddah", "0566410385", "Tahlia St 40", "Jeddah"),
	("خالد الشمري", "Individual", "Individual", "Riyadh", "0590336742", "حي النرجس", "Riyadh"),
]


# ------------------------------------------------------------------------------ log
def _log_path():
	return frappe.get_site_path("private", "files", LOG_FILE)


def _load_log():
	path = _log_path()
	if os.path.exists(path):
		with open(path) as f:
			return json.load(f)
	return []


def _save_log(log):
	os.makedirs(os.path.dirname(_log_path()), exist_ok=True)
	with open(_log_path(), "w") as f:
		json.dump(log, f, indent=1, ensure_ascii=False)


class _Recorder:
	def __init__(self):
		self.log = _load_log()

	def add(self, doctype, name):
		if [doctype, name] not in self.log:
			self.log.append([doctype, name])

	def insert(self, doc, submit=False):
		doc.insert()
		if submit:
			doc.submit()
		self.add(doc.doctype, doc.name)
		return doc

	def ensure(self, doctype, name, values):
		if frappe.db.exists(doctype, name):
			return frappe.get_doc(doctype, name)
		return self.insert(frappe.get_doc({"doctype": doctype, **values}))

	def from_result(self, result):
		for d in result.get("documents") or []:
			self.add(d["doctype"], d["name"])
		return result


def _ref():
	return "demo-" + uuid.uuid4().hex[:16]


# ------------------------------------------------------------------------------ create
def create():
	"""Create demo masters, stock and orders in every status. Safe to run once."""
	if frappe.session.user in ("Guest", None):
		frappe.set_user("Administrator")
	if frappe.db.exists("Item", "DEMO-T001"):
		print("Demo data already exists. Run ksa_retail.demo.remove first to recreate it.")
		return

	rec = _Recorder()
	s = get_context()
	company, wh = s.company, s.warehouse
	if not s.tax_template:
		frappe.throw("Create a default Sales Taxes and Charges Template (VAT 15%) first.")

	try:
		_masters(rec, company)
		_stock(rec, company, wh)
		customers = _customers(rec)
		supplier = _supplier(rec)
		_orders(rec, customers, supplier)
	except Exception:
		frappe.db.rollback()
		raise
	finally:
		_save_log(rec.log)
	frappe.db.commit()
	print(f"Demo data created: {len(rec.log)} records. Open /ksa-pos and search for 'الحربي' or '0551'.")


def _masters(rec, company):
	for name in ("Riyadh", "Jeddah", "Dammam"):
		rec.ensure("Territory", name, {"territory_name": name, "parent_territory": "Saudi Arabia"})
	for brand, abbr, _country in BRANDS:
		rec.ensure("Brand", brand, {"brand": brand, "custom_abbreviation": abbr})
	if not frappe.db.exists("Payment Terms Template", "Cash POS Demo"):
		rec.ensure(
			"Payment Terms Template",
			"Cash POS Demo",
			{
				"template_name": "Cash POS Demo",
				"terms": [
					{
						"invoice_portion": 100,
						"credit_days": 0,
						"due_date_based_on": "Day(s) after invoice date",
					}
				],
			},
		)
	years = {y for *_x, stock in ITEMS for y in stock} | {"2024", "2025", "2026"}
	for y in sorted(years):
		rec.ensure("Production Year", y, {"production_year": y})

	uom = "Unit" if frappe.db.exists("UOM", "Unit") else "Nos"
	group = "Products" if frappe.db.exists("Item Group", "Products") else "All Item Groups"
	abbr = {b: a for b, a, _c in BRANDS}
	country = {b: c for b, _a, c in BRANDS}
	for code, brand, size, ply, pattern, price, buying, _stock in ITEMS:
		rec.ensure("Tire Size", size, {"tire_size": size})
		if not frappe.db.exists("Country", country[brand]):
			country[brand] = "Saudi Arabia"
		rec.ensure(
			"Item",
			code,
			{
				"item_code": code,
				"item_name": f"{abbr[brand]} {size} | {ply} | {pattern}",
				"item_group": group,
				"stock_uom": uom,
				"brand": brand,
				"is_stock_item": 1,
				"has_batch_no": 0,
				"country_of_origin": country[brand],
				"tire_size": size,
				"ply_rating": ply,
				"tire_pattern": pattern,
				"description": "KSA Retail POS demo item",
			},
		)
		frappe.db.set_value("Item", code, "item_code", code)  # keep demo codes even if a naming script runs
		rec.insert(
			frappe.get_doc(
				{
					"doctype": "Item Price",
					"item_code": code,
					"price_list": get_context().price_list,
					"price_list_rate": price,
				}
			)
		)
		if frappe.db.exists("Price List", "Standard Buying"):
			rec.insert(
				frappe.get_doc(
					{
						"doctype": "Item Price",
						"item_code": code,
						"price_list": "Standard Buying",
						"price_list_rate": buying,
					}
				)
			)


def _stock(rec, company, wh):
	rows = []
	for code, *_x, buying, stock in [(i[0], i[6], i[7]) for i in ITEMS]:
		for year, qty in stock.items():
			rows.append(
				{
					"item_code": code,
					"qty": qty,
					"t_warehouse": wh,
					"basic_rate": buying,
					"to_production_year": year,
				}
			)
	se = frappe.get_doc(
		{
			"doctype": "Stock Entry",
			"stock_entry_type": "Material Receipt",
			"company": company,
			"remarks": "KSA Retail POS demo opening stock",
			"items": rows,
		}
	)
	rec.insert(se, submit=True)


def _customers(rec):
	terms = "Cash POS Demo"
	out = []
	for name, ctype, group, terr, mobile, line1, city in CUSTOMERS:
		existing = frappe.db.get_value("Customer", {"customer_name": name})
		if existing:
			out.append(existing)
			continue
		c = frappe.get_doc(
			{
				"doctype": "Customer",
				"customer_name": name,
				"customer_type": ctype,
				"customer_group": group
				if frappe.db.exists("Customer Group", group)
				else "All Customer Groups",
				"territory": terr,
				"payment_terms": terms,
				"mobile_no": mobile,
				"address_line1": line1,
				"city": city,
				"country": "Saudi Arabia",
			}
		)
		rec.insert(c)
		for dt, link in (("Address", c.customer_primary_address), ("Contact", c.customer_primary_contact)):
			if link:
				rec.add(dt, link)
		out.append(c.name)
	return out


def _supplier(rec):
	name = frappe.db.get_value("Supplier", {"supplier_name": "Pirelli Saudi Distributor"})
	if name:
		return name
	group = (
		"Distributor"
		if frappe.db.exists("Supplier Group", "Distributor")
		else frappe.db.get_value("Supplier Group", {"is_group": 0})
	)
	return rec.insert(
		frappe.get_doc(
			{
				"doctype": "Supplier",
				"supplier_name": "Pirelli Saudi Distributor",
				"supplier_group": group,
				"supplier_type": "Company",
			}
		)
	).name


def _orders(rec, customers, supplier):
	main, faisal, nukhba, waha, khaled = customers

	def tx(
		customer,
		sales_order=None,
		items=None,
		action=None,
		payments=None,
		lines=None,
		drop_ship=None,
		discount=None,
	):
		"""Same calls the POS page makes for each cashier action."""
		ref = _ref()
		if items:
			result = sales.create_sale(
				client_ref=ref, customer=customer, lines=items, discount=discount, payments=payments,
				deliver=1 if action == "deliver" else 0, drop_ship=drop_ship,
			)  # fmt: skip
		elif action == "deliver":
			result = sales.deliver_order(
				client_ref=ref, sales_order=sales_order, quantities=lines, payments=payments
			)
		elif action == "invoice":
			result = sales.invoice_order(
				client_ref=ref, sales_order=sales_order, quantities=lines, payments=payments
			)
		else:
			result = sales.register_payment(
				client_ref=ref, customer=customer, sales_order=sales_order, payments=payments
			)
		return rec.from_result(result)

	def line(code, qty, year=None):
		return {"item_code": code, "qty": qty, "dims": {"production_year": year} if year else {}}

	def cash(amount):
		return [{"mode_of_payment": "Cash", "amount": amount}]

	# 1. complete: paid, delivered, invoiced
	r = tx(customer=main, items=[line("DEMO-T007", 4, "2024")], payments=cash(1518))
	so = r["order"]["name"]
	tx(customer=main, sales_order=so, action="deliver")
	tx(customer=main, sales_order=so, action="invoice")

	# 2. drop-ship: supplier delivered, invoiced, paid
	r = tx(
		customer=main,
		items=[dict(line("DEMO-T008", 4, "2025"), drop_ship=1)],
		action="deliver",
		drop_ship={"supplier": supplier},
	)
	so = r["order"]["name"]
	tx(customer=main, sales_order=so, action="invoice", payments=cash(4508))

	# 3. invoiced + delivered, partly paid, one tyre returned
	r = tx(
		customer=main,
		items=[line("DEMO-T002", 8, "2026"), line("DEMO-T001", 4, "2024")],
		discount={"type": "pct", "value": 5},
	)
	so = r["order"]["name"]
	tx(customer=main, sales_order=so, action="deliver")
	r = tx(customer=main, sales_order=so, action="invoice", payments=cash(3000))
	tyre = next(x for x in r["order"]["lines"] if x["item_code"] == "DEMO-T001")
	rec.from_result(sales.return_items(client_ref=_ref(), sales_order=so, quantities={tyre["so_detail"]: 1}))

	# 4. delivered, not invoiced, not paid
	r = tx(customer=main, items=[line("DEMO-T003", 4, "2025")])
	tx(customer=main, sales_order=r["order"]["name"], action="deliver")

	# 5. advance payment: paid in full, waiting for delivery and invoice
	tx(customer=main, items=[line("DEMO-T001", 4, "2025"), line("DEMO-T005", 2, "2026")], payments=cash(3335))

	# 6. delivered and invoiced, nothing paid yet
	r = tx(customer=main, items=[line("DEMO-T006", 4, "2025")], action="deliver")
	tx(customer=main, sales_order=r["order"]["name"], action="invoice")

	# 7. partial delivery (2 of 4)
	r = tx(customer=main, items=[line("DEMO-T004", 4, "2026")], payments=cash(1000))
	l = r["order"]["lines"][0]
	tx(customer=main, sales_order=r["order"]["name"], action="deliver", lines={l["so_detail"]: 2})

	# other customers
	r = tx(customer=faisal, items=[line("DEMO-T005", 4, "2026")], payments=cash(1200))
	tx(customer=faisal, sales_order=r["order"]["name"], action="deliver")
	r = tx(customer=nukhba, items=[line("DEMO-T006", 8, "2025"), line("DEMO-T004", 4, "2024")])
	tx(customer=nukhba, sales_order=r["order"]["name"], action="deliver")
	tx(customer=nukhba, sales_order=r["order"]["name"], action="invoice", payments=cash(5000))
	tx(customer=waha, payments=cash(1500))  # advance credit without an order
	r = tx(customer=khaled, items=[line("DEMO-T007", 4, "2025")], payments=cash(1518))
	tx(customer=khaled, sales_order=r["order"]["name"], action="deliver")
	tx(customer=khaled, sales_order=r["order"]["name"], action="invoice")


# ------------------------------------------------------------------------------ remove
CANCEL_ORDER = [
	"Payment Entry",
	"Sales Invoice",
	"Delivery Note",
	"Purchase Order",
	"Sales Order",
	"Stock Entry",
]


def remove():
	"""Cancel and delete every record the demo created (and nothing else)."""
	if frappe.session.user in ("Guest", None):
		frappe.set_user("Administrator")
	log = _load_log()
	if not log:
		print("No demo data recorded.")
		return

	# documents created later by the POS for demo customers (e.g. while presenting) go too
	demo_customers = [n for dt, n in log if dt == "Customer"]
	for dt, field in (
		("Payment Entry", "party"),
		("Sales Invoice", "customer"),
		("Delivery Note", "customer"),
		("Sales Order", "customer"),
	):
		for name in frappe.get_all(dt, filters={field: ["in", demo_customers or ["-"]]}, pluck="name"):
			if [dt, name] not in log:
				log.append([dt, name])
	for name in frappe.get_all(
		"Purchase Order Item",
		filters={"sales_order": ["in", [n for d, n in log if d == "Sales Order"] or ["-"]]},
		pluck="parent",
	):
		if ["Purchase Order", name] not in log:
			log.append(["Purchase Order", name])

	tx = [x for x in log if x[0] in CANCEL_ORDER]
	tx.sort(key=lambda x: (CANCEL_ORDER.index(x[0]), -log.index(x)))
	failed = []
	for dt, name in tx:
		if not frappe.db.exists(dt, name):
			continue
		try:
			doc = frappe.get_doc(dt, name)
			if doc.docstatus == 1:
				doc.flags.ignore_links = True
				doc.cancel()
			frappe.delete_doc(dt, name, force=1, ignore_permissions=True)
			frappe.db.commit()
		except Exception as e:
			frappe.db.rollback()
			failed.append(f"{dt} {name}: {e}")

	for dt, name in reversed([x for x in log if x[0] not in CANCEL_ORDER]):
		if not frappe.db.exists(dt, name):
			continue
		try:
			frappe.delete_doc(dt, name, force=1, ignore_permissions=True)
			frappe.db.commit()
		except Exception as e:
			frappe.db.rollback()
			failed.append(f"{dt} {name}: {e}")

	if failed:
		_save_log([x for x in log if frappe.db.exists(*x)])
		print("Removed with some leftovers:\n  " + "\n  ".join(failed))
	else:
		os.remove(_log_path())
		print(f"Demo data removed ({len(log)} records).")
