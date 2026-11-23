"""Business scenarios end to end, through the whitelisted endpoints.

Run with `ksa_retail.pos.tests.runner.run` (everything is rolled back). The scenarios
share one customer and build on each other, so the test methods are ordered.
"""

import typing
import unittest
import uuid

import frappe
from frappe.utils import flt, nowdate

from ksa_retail.pos import context, dimensions, fulfilment, idempotency, payments, stock
from ksa_retail.pos.api import catalog, customers, orders, session
from ksa_retail.pos.api import sales as sales_api

PREFIX = "KSA-POS-TEST"


class _Request:
	"""Call endpoints like separate web requests: the transaction "commits" after each call.
	Under the test runner a commit only fires the after-commit callbacks (no real commit),
	which is what releases duplicate-protection locks and stores replayable results."""

	def __init__(self, module):
		self._module = module

	def __getattr__(self, name):
		endpoint = getattr(self._module, name)

		def call(*args, **kwargs):
			result = endpoint(*args, **kwargs)
			frappe.db.commit()
			return result

		return call


sales = _Request(sales_api)


def ref() -> str:
	return uuid.uuid4().hex


def doctypes(result) -> list[str]:
	return [d["doctype"] for d in result["documents"]]


def first(result, doctype) -> str:
	return next(d["name"] for d in result["documents"] if d["doctype"] == doctype)


def line_of(order, item_code, year=None):
	return next(
		line
		for line in order["lines"]
		if line["item_code"] == item_code and (year is None or line["dims"].get("production_year") == year)
	)


class TestPosScenarios(unittest.TestCase):
	company = None
	customer = None
	supplier = None
	state: typing.ClassVar[dict] = {}

	# ------------------------------------------------------------------ fixtures
	@classmethod
	def setUpClass(cls):
		if not frappe.flags.ksa_pos_rollback_run:
			raise unittest.SkipTest("Run through ksa_retail.pos.tests.runner.run (it rolls everything back).")
		frappe.set_user("Administrator")
		cls.company = context.get_context().company
		cls.warehouse = context.get_context().warehouse
		company = cls.company
		for year in ("2024", "2025"):
			if not frappe.db.exists("Production Year", year):
				frappe.get_doc({"doctype": "Production Year", "production_year": year}).insert()
		if not frappe.db.get_value("Sales Taxes and Charges Template", {"company": company, "is_default": 1}):
			frappe.get_doc(
				{
					"doctype": "Sales Taxes and Charges Template",
					"title": f"{PREFIX} VAT",
					"company": company,
					"is_default": 1,
					"taxes": [
						{
							"charge_type": "On Net Total",
							"account_head": frappe.db.get_value(
								"Account", {"company": company, "account_type": "Tax", "is_group": 0}
							),
							"rate": 15,
							"description": "VAT 15%",
						}
					],
				}
			).insert()
		bank = frappe.db.get_value(
			"Account", {"company": company, "account_type": "Bank", "is_group": 0}
		) or (
			frappe.get_doc(
				{
					"doctype": "Account",
					"account_name": f"{PREFIX} Bank",
					"company": company,
					"account_type": "Bank",
					"parent_account": frappe.db.get_value(
						"Account", {"company": company, "account_name": "Bank Accounts"}
					),
				}
			)
			.insert()
			.name
		)
		wire = frappe.get_doc("Mode of Payment", "Wire Transfer")
		if not any(a.company == company for a in wire.accounts):
			wire.append("accounts", {"company": company, "default_account": bank})
			wire.save()
		if not frappe.db.exists("Brand", "Michelin"):
			frappe.get_doc({"doctype": "Brand", "brand": "Michelin", "custom_abbreviation": "MIC"}).insert()
		size = (
			frappe.db.exists("Tire Size", "205/55 R16")
			or frappe.get_doc({"doctype": "Tire Size", "tire_size": "205/55 R16"}).insert().name
		)
		for code, name, rate, is_stock in (
			("T-MIC", "Michelin Primacy 4 205/55 R16", 400, 1),
			("T-VAL", "Valve TR414", 10, 1),
			("T-DROP", "Pirelli Scorpion 265/65 R17", 600, 0),
		):
			frappe.get_doc(
				{
					"doctype": "Item",
					"item_code": code,
					"item_name": name,
					"item_group": "Products"
					if frappe.db.exists("Item Group", "Products")
					else "All Item Groups",
					"stock_uom": "Nos",
					"is_stock_item": is_stock,
					"brand": "Michelin",
					"country_of_origin": "Saudi Arabia",
					"tire_size": size,
					"ply_rating": "P04",
					"tire_pattern": "Primacy",
					"has_batch_no": 1 if code == "T-MIC" else 0,
					"create_new_batch": 1,
					"batch_number_series": f"{code}-.####",
				}
			).insert()
			frappe.get_doc(
				{
					"doctype": "Item Price",
					"item_code": code,
					"price_list": context.get_context().price_list,
					"price_list_rate": rate,
				}
			).insert()
		receipt = frappe.get_doc(
			{
				"doctype": "Stock Entry",
				"stock_entry_type": "Material Receipt",
				"company": company,
				"items": [
					{
						"item_code": "T-MIC",
						"qty": 10,
						"t_warehouse": cls.warehouse,
						"basic_rate": 250,
						"to_production_year": "2024",
					},
					{
						"item_code": "T-MIC",
						"qty": 20,
						"t_warehouse": cls.warehouse,
						"basic_rate": 260,
						"to_production_year": "2025",
					},
					{
						"item_code": "T-VAL",
						"qty": 100,
						"t_warehouse": cls.warehouse,
						"basic_rate": 3,
						"to_production_year": "2025",
					},
				],
			}
		)
		receipt.insert()
		receipt.submit()
		terms = (
			frappe.db.exists("Payment Terms Template", f"{PREFIX} Cash")
			or frappe.get_doc(
				{
					"doctype": "Payment Terms Template",
					"template_name": f"{PREFIX} Cash",
					"terms": [
						{
							"invoice_portion": 100,
							"credit_days": 0,
							"due_date_based_on": "Day(s) after invoice date",
						}
					],
				}
			)
			.insert()
			.name
		)
		cls.supplier = (
			frappe.get_doc(
				{
					"doctype": "Supplier",
					"supplier_name": f"{PREFIX} Supplier",
					"supplier_group": frappe.db.get_value("Supplier Group", {"is_group": 0}),
				}
			)
			.insert()
			.name
		)
		context.clear_cache()
		dimensions.clear_cache()
		created = customers.register_customer(
			{
				"customer_name": f"{PREFIX} Buyer",
				"customer_type": "Individual",
				"customer_group": "Individual",
				"territory": "Saudi Arabia",
				"payment_terms": terms,
				"mobile_no": "0551112222",
				"address_line1": "King Fahd Rd",
				"city": "Riyadh",
				"country": "Saudi Arabia",
			}
		)
		cls.customer = created["name"]
		cls.state["registered"] = created

	def setUp(self):
		frappe.set_user("Administrator")

	def assertFails(self, operation, contains=""):
		frappe.db.savepoint("ksa_pos_test")
		with self.assertRaises(Exception) as caught:
			operation()
		frappe.db.rollback(save_point="ksa_pos_test")
		frappe.clear_messages()
		self.assertIn(contains.lower(), str(caught.exception).lower())

	def sale(self, lines, **kwargs):
		return sales.create_sale(
			client_ref=kwargs.pop("client_ref", ref()), customer=self.customer, lines=lines, **kwargs
		)

	def bucket_key(self, year):
		return tuple(year if d.source == "production_year" else "" for d in dimensions.get_dimensions())

	# ------------------------------------------------------------------ setup / search
	def test_00_registration_and_boot(self):
		self.assertTrue(self.state["registered"]["has_address"])
		from ksa_retail.pos.boot import get_boot

		boot = get_boot()
		self.assertEqual(boot["dimensions"][0]["fieldname"], "production_year")
		wire = next(m for m in boot["settings"]["payment_modes"] if m["name"] == "Wire Transfer")
		self.assertTrue(wire["requires_reference"])
		self.assertTrue(context.get_context().tax_template)

	def test_01_search(self):
		mic = next(i for i in catalog.search_items("Michelin")["items"] if i.item_code == "T-MIC")
		self.assertEqual(
			{s["dims"]["production_year"]: s["available"] for s in mic.stock}, {"2024": 10, "2025": 20}
		)
		self.assertTrue(
			any(i.item_code == "T-MIC" for i in catalog.search_items("", brand="Michelin")["items"])
		)
		self.assertTrue(any(c.name == self.customer for c in customers.search_customers("055 111")))
		self.assertTrue(any(c.name == self.customer for c in customers.search_customers(f"{PREFIX} Buy")))
		self.assertTrue(
			any(c.name == self.customer for c in customers.search_customers("Saudi Arabia", limit=50))
		)

	# ------------------------------------------------------------------ 1. normal sale
	def test_10_normal_sale(self):
		lines = [
			{"item_code": "T-MIC", "qty": 4, "dims": {"production_year": "2024"}},
			{"item_code": "T-VAL", "qty": 4, "dims": {"production_year": "2025"}},
		]
		quote = catalog.quote_sale(self.customer, lines, {"type": "pct", "value": 10})
		self.assertAlmostEqual(quote["grand_total"], 1640 * 0.9 * 1.15, delta=0.02)

		client_ref = ref()
		result = self.sale(
			lines,
			client_ref=client_ref,
			discount={"type": "pct", "value": 10},
			payments=[
				{"mode_of_payment": "Cash", "amount": 1000},
				{
					"mode_of_payment": "Wire Transfer",
					"amount": round(quote["rounded_total"] - 1000, 2),
					"reference_no": "TRX-1",
				},
			],
		)
		order = result["order"]
		self.assertEqual(doctypes(result), ["Sales Order", "Payment Entry", "Payment Entry"])
		self.assertAlmostEqual(order["total"], quote["rounded_total"], delta=0.01)
		self.assertEqual(
			(order["status"]["payment"], order["status"]["invoice"], order["status"]["delivery"]),
			("done", "pending", "pending"),
		)
		references = frappe.get_all(
			"Payment Entry Reference",
			filters={"parent": ["in", [d["name"] for d in result["documents"][1:]]]},
			pluck="reference_name",
		)
		self.assertEqual(set(references), {order["name"]})
		self.assertEqual(
			frappe.db.get_value(
				"Sales Order Item", {"parent": order["name"], "item_code": "T-MIC"}, "production_year"
			),
			"2024",
		)

		replay = self.sale(lines, client_ref=client_ref)
		self.assertEqual(replay["order"]["name"], order["name"])
		self.assertEqual(frappe.db.count("Sales Order", {"customer": self.customer}), 1)

		delivered = sales.deliver_order(client_ref=ref(), sales_order=order["name"])
		delivery = delivered["documents"][0]["name"]
		self.assertEqual(
			frappe.db.get_value(
				"Delivery Note Item", {"parent": delivery, "item_code": "T-MIC"}, "production_year"
			),
			"2024",
		)
		for row in frappe.get_all(
			"Delivery Note Item", filters={"parent": delivery, "item_code": "T-MIC"}, fields=["batch_no"]
		):
			received_year = frappe.db.sql(
				"""select sle.production_year from `tabStock Ledger Entry` sle
				join `tabSerial and Batch Entry` e on e.parent = sle.serial_and_batch_bundle
				where e.batch_no = %s and sle.voucher_type = 'Stock Entry' limit 1""",
				row.batch_no,
			)[0][0]
			self.assertEqual(received_year, "2024", "batch must come from the ordered production year")
		ledger = frappe.db.get_value(
			"Stock Ledger Entry",
			{"voucher_no": delivery, "item_code": "T-MIC"},
			["actual_qty", "production_year"],
		)
		self.assertEqual(tuple(ledger), (-4, "2024"))

		invoiced = sales.invoice_order(client_ref=ref(), sales_order=order["name"])
		invoice = frappe.get_doc("Sales Invoice", invoiced["documents"][0]["name"])
		self.assertTrue(
			all(i.delivery_note == delivery and i.sales_order == order["name"] for i in invoice.items)
		)
		self.assertEqual(flt(invoice.outstanding_amount), 0)
		final = invoiced["order"]
		self.assertTrue(all(final["status"][k] == "done" for k in ("payment", "invoice", "delivery")))
		self.assertAlmostEqual(final["paid"], final["total"], delta=0.01)
		self.assertEqual(frappe.db.get_value("Delivery Note", delivery, "per_billed"), 100)
		self.assertTrue(final["edit_block"])
		self.assertFails(
			lambda: sales.update_order(
				client_ref=ref(), sales_order=order["name"], lines=[{"item_code": "T-MIC", "qty": 1}]
			),
			"invoice",
		)
		self.state.update(order1=order["name"], delivery1=delivery, invoice1=invoice.name, quote1=quote)

	# ------------------------------------------------------------------ 2. invoice delivered qty only
	def test_20_invoice_delivered_quantity_only(self):
		lines = [{"item_code": "T-MIC", "qty": 3, "dims": {"production_year": "2025"}}]
		result = self.sale(lines)
		order = result["order"]
		line = order["lines"][0]
		self.assertFalse(order["can_invoice"])
		self.assertEqual(line["pending_billing"], 0)
		self.assertFails(
			lambda: sales.invoice_order(client_ref=ref(), sales_order=order["name"]), "nothing delivered"
		)

		result = sales.deliver_order(
			client_ref=ref(), sales_order=order["name"], quantities={line["so_detail"]: 2}
		)
		delivery = result["documents"][0]["name"]
		self.assertEqual(result["order"]["lines"][0]["pending_billing"], 2)
		self.assertTrue(result["order"]["can_invoice"])
		result = sales.invoice_order(client_ref=ref(), sales_order=order["name"])
		invoice = first(result, "Sales Invoice")
		rows = frappe.get_all(
			"Sales Invoice Item", filters={"parent": invoice}, fields=["qty", "delivery_note"]
		)
		self.assertEqual([(r.qty, r.delivery_note) for r in rows], [(2.0, delivery)])
		self.assertEqual(
			(result["order"]["status"]["invoice"], result["order"]["status"]["delivery"]), ("part", "part")
		)
		self.assertFails(
			lambda: sales.invoice_order(client_ref=ref(), sales_order=order["name"]), "nothing delivered"
		)

		result = sales.register_payment(
			client_ref=ref(),
			customer=self.customer,
			sales_order=order["name"],
			payments=[{"mode_of_payment": "Cash", "amount": 500}],
		)
		self.assertEqual(
			frappe.get_all(
				"Payment Entry Reference",
				filters={"parent": result["documents"][0]["name"]},
				pluck="reference_name",
			),
			[invoice],
		)
		self.assertEqual(result["order"]["status"]["payment"], "part")
		self.assertAlmostEqual(result["order"]["paid"], 500, delta=0.01)
		self.assertEqual(
			sales.deliver_order(client_ref=ref(), sales_order=order["name"])["order"]["status"]["delivery"],
			"done",
		)
		self.assertEqual(
			sales.invoice_order(client_ref=ref(), sales_order=order["name"])["order"]["status"]["invoice"],
			"done",
		)
		self.state.update(order2=order["name"], invoice2=invoice)

	# ------------------------------------------------------------------ 3. payments
	def test_30_payment_without_order(self):
		result = sales.register_payment(
			client_ref=ref(), customer=self.customer, payments=[{"mode_of_payment": "Cash", "amount": 300}]
		)
		entry = frappe.get_doc("Payment Entry", result["documents"][0]["name"])
		self.assertEqual(entry.references[0].reference_name, self.state["invoice2"])
		self.assertAlmostEqual(
			entry.unallocated_amount, max(0, 300 - entry.references[0].allocated_amount), delta=0.01
		)
		self.assertFails(
			lambda: sales.register_payment(
				client_ref=ref(),
				customer=self.customer,
				payments=[{"mode_of_payment": "Wire Transfer", "amount": 50}],
			),
			"reference",
		)
		self.assertFails(
			lambda: sales.register_payment(client_ref=ref(), customer=self.customer, payments=[]),
			"payment amount",
		)

	# ------------------------------------------------------------------ 4. partial delivery + editing
	def test_40_partial_delivery_and_editing(self):
		result = self.sale(
			[
				{"item_code": "T-MIC", "qty": 5, "dims": {"production_year": "2025"}},
				{"item_code": "T-VAL", "qty": 2, "dims": {"production_year": "2025"}},
			],
			payments=[{"mode_of_payment": "Cash", "amount": 200}],
		)
		order_name = result["order"]["name"]
		mic = line_of(result["order"], "T-MIC")
		result = sales.deliver_order(
			client_ref=ref(), sales_order=order_name, quantities={mic["so_detail"]: 2}
		)
		self.assertEqual(result["order"]["status"]["delivery"], "part")
		self.assertEqual(line_of(result["order"], "T-MIC")["delivered_qty"], 2)
		delivery = result["documents"][0]["name"]
		self.assertIsNone(result["order"]["edit_block"])

		result = sales.update_order(
			client_ref=ref(),
			sales_order=order_name,
			lines=[
				{
					"so_detail": mic["so_detail"],
					"item_code": "T-MIC",
					"qty": 1,
					"dims": {"production_year": "2025"},
				},
				{"item_code": "T-MIC", "qty": 2, "dims": {"production_year": "2024"}},
			],
		)
		actions = [(d["doctype"], d["action"]) for d in result["documents"]]
		self.assertIn(("Delivery Note", "cancelled"), actions)
		self.assertIn(("Delivery Note", "created"), actions)
		self.assertEqual(frappe.db.get_value("Delivery Note", delivery, "docstatus"), 2)
		by_key = {(l["item_code"], l["dims"].get("production_year")): l for l in result["order"]["lines"]}
		self.assertEqual(set(by_key), {("T-MIC", "2025"), ("T-MIC", "2024")})
		self.assertEqual(
			(by_key[("T-MIC", "2025")]["qty"], by_key[("T-MIC", "2025")]["delivered_qty"]), (1, 1)
		)
		self.assertAlmostEqual(result["order"]["paid"], 200, delta=0.01)

		result = sales.update_order(
			client_ref=ref(),
			sales_order=order_name,
			lines=[
				{
					"so_detail": by_key[("T-MIC", "2025")]["so_detail"],
					"item_code": "T-MIC",
					"qty": 1,
					"dims": {"production_year": "2025"},
				},
				{
					"so_detail": by_key[("T-MIC", "2024")]["so_detail"],
					"item_code": "T-MIC",
					"qty": 3,
					"rate": 380,
					"dims": {"production_year": "2024"},
				},
			],
		)
		self.assertEqual(result["documents"], [])
		self.assertTrue(any(l["qty"] == 3 and l["rate"] == 380 for l in result["order"]["lines"]))
		self.assertIsNone(orders.get_order(order_name)["edit_block"])
		self.state["order4"] = order_name

	# ------------------------------------------------------------------ 5. stock
	def test_50_insufficient_stock(self):
		self.assertFails(
			lambda: self.sale([{"item_code": "T-MIC", "qty": 9, "dims": {"production_year": "2024"}}]),
			"available",
		)
		self.assertFails(
			lambda: sales.update_order(
				client_ref=ref(),
				sales_order=self.state["order4"],
				lines=[{"item_code": "T-MIC", "qty": 50, "dims": {"production_year": "2025"}}],
			),
			"available",
		)
		self.assertFails(lambda: self.sale([{"item_code": "T-MIC", "qty": 1}]), "production year")

	# ------------------------------------------------------------------ 6. supplier delivers directly
	def test_60_supplier_direct_delivery(self):
		result = self.sale(
			[{"item_code": "T-DROP", "qty": 4, "dims": {"production_year": "2025"}, "drop_ship": 1}],
			deliver=1,
			drop_ship={"supplier": self.supplier, "bill_no": "SUP-100"},
		)
		self.assertEqual(doctypes(result), ["Sales Order", "Purchase Order", "Purchase Invoice"])
		self.assertEqual(result["order"]["status"]["delivery"], "done")
		purchase_order = first(result, "Purchase Order")
		purchase_invoice = frappe.get_doc("Purchase Invoice", first(result, "Purchase Invoice"))
		self.assertEqual(purchase_invoice.update_stock, 0)
		self.assertFalse(frappe.db.exists("Stock Ledger Entry", {"voucher_no": purchase_invoice.name}))
		self.assertEqual(purchase_invoice.items[0].production_year, "2025")
		self.assertEqual(frappe.db.get_value("Purchase Order", purchase_order, "per_billed"), 100)
		self.assertFalse(result["order"]["supplier_unbilled"])
		self.assertEqual(frappe.db.get_value("Purchase Order", purchase_order, "status"), "Delivered")
		self.assertEqual(result["order"]["documents"]["Purchase Order"][0]["name"], purchase_order)

		purchase_invoice.cancel()
		order_name = result["order"]["name"]
		self.assertTrue(orders.get_order(order_name)["supplier_unbilled"])
		self.assertFails(
			lambda: sales.bill_supplier(client_ref=ref(), sales_order=order_name), "invoice number"
		)
		billed = sales.bill_supplier(client_ref=ref(), sales_order=order_name, bill_no="SUP-778")
		rebilled = frappe.get_doc("Purchase Invoice", billed["documents"][0]["name"])
		self.assertEqual((rebilled.bill_no, rebilled.update_stock), ("SUP-778", 0))
		self.assertFalse(billed["order"]["supplier_unbilled"])

		rebilled.cancel()  # Desk guard: Update Stock forced off on a drop-ship supplier invoice
		from erpnext.buying.doctype.purchase_order.purchase_order import make_purchase_invoice

		desk_invoice = make_purchase_invoice(purchase_order)
		desk_invoice.update_stock = 1
		desk_invoice.bill_no = "SUP-DESK"
		for row in desk_invoice.items:
			row.production_year = "2025"
		fulfilment.set_purchase_taxes(desk_invoice)
		desk_invoice.insert()
		self.assertEqual(desk_invoice.update_stock, 0)

		self.assertEqual(
			sales.invoice_order(client_ref=ref(), sales_order=order_name)["order"]["status"]["invoice"],
			"done",
		)

		later = self.sale(
			[{"item_code": "T-DROP", "qty": 1, "dims": {"production_year": "2025"}, "drop_ship": 1}],
			deliver=1,
			drop_ship={"supplier": self.supplier},
		)
		self.assertEqual(doctypes(later), ["Sales Order", "Purchase Order"])
		self.assertTrue(later["order"]["supplier_unbilled"])

	# ------------------------------------------------------------------ 7. returns
	def test_70_returns(self):
		order1 = orders.get_order(self.state["order1"])
		mic = line_of(order1, "T-MIC")
		self.assertEqual(mic["returnable"], 4)
		on_hand = stock.get_stock(["T-MIC"], self.warehouse)["T-MIC"][self.bucket_key("2024")]["on_hand"]
		credit = round(400 * 0.9 * 1.15, 2)
		result = sales.return_items(
			client_ref=ref(),
			sales_order=self.state["order1"],
			quantities={mic["so_detail"]: 1},
			refunds=[{"mode_of_payment": "Cash", "amount": credit}],
		)
		self.assertEqual(doctypes(result), ["Delivery Note", "Sales Invoice", "Payment Entry"])
		return_delivery, credit_note, _refund = [d["name"] for d in result["documents"]]
		self.assertEqual(
			stock.get_stock(["T-MIC"], self.warehouse)["T-MIC"][self.bucket_key("2024")]["on_hand"],
			on_hand + 1,
		)
		returned = frappe.db.get_value(
			"Delivery Note", return_delivery, ["is_return", "return_against"], as_dict=True
		)
		self.assertEqual((returned.is_return, returned.return_against), (1, self.state["delivery1"]))
		note = frappe.db.get_value(
			"Sales Invoice", credit_note, ["is_return", "return_against", "outstanding_amount"], as_dict=True
		)
		self.assertEqual((note.is_return, note.return_against), (1, self.state["invoice1"]))
		self.assertAlmostEqual(note.outstanding_amount, 0, delta=0.01)
		rows = frappe.get_all(
			"Sales Invoice Item", filters={"parent": credit_note}, fields=["delivery_note", "sales_order"]
		)
		self.assertTrue(
			rows
			and all(
				r.delivery_note == return_delivery and r.sales_order == self.state["order1"] for r in rows
			)
		)
		order = result["order"]
		self.assertAlmostEqual(order["total"], self.state["quote1"]["rounded_total"] - credit, delta=0.02)
		self.assertEqual(order["status"]["payment"], "done")
		self.assertEqual(line_of(order, "T-MIC")["returnable"], 3)
		self.assertFails(
			lambda: sales.return_items(
				client_ref=ref(), sales_order=self.state["order1"], quantities={mic["so_detail"]: 9}
			),
			"at most",
		)

		order2 = orders.get_order(self.state["order2"])
		outstanding = order2["outstanding"]
		result = sales.return_items(
			client_ref=ref(),
			sales_order=self.state["order2"],
			quantities={order2["lines"][0]["so_detail"]: 1},
		)
		self.assertEqual(doctypes(result), ["Delivery Note", "Sales Invoice"])
		return_delivery = first(result, "Delivery Note")
		credit_rows = frappe.get_all(
			"Sales Invoice Item", filters={"parent": first(result, "Sales Invoice")}, pluck="delivery_note"
		)
		self.assertTrue(all(r == return_delivery for r in credit_rows))
		self.assertEqual(frappe.db.get_value("Delivery Note", return_delivery, "per_billed"), 100)
		self.assertAlmostEqual(result["order"]["outstanding"], outstanding - 460, delta=0.02)

		order4 = orders.get_order(self.state["order4"])
		delivered_line = next(l for l in order4["lines"] if l["delivered_qty"] > 0)
		result = sales.return_items(
			client_ref=ref(), sales_order=self.state["order4"], quantities={delivered_line["so_detail"]: 1}
		)
		self.assertEqual(doctypes(result), ["Delivery Note"])

	# ------------------------------------------------------------------ 8. advances and credit
	def test_80_advances_and_credit(self):
		from erpnext.selling.doctype.sales_order.sales_order import make_sales_invoice

		result = self.sale(
			[{"item_code": "T-MIC", "qty": 1, "dims": {"production_year": "2025"}}],
			payments=[{"mode_of_payment": "Cash", "amount": 200}],
		)
		order_name, advance = result["order"]["name"], first(result, "Payment Entry")
		frappe.message_log = []
		desk_invoice = make_sales_invoice(order_name)
		desk_invoice.allocate_advances_automatically = 0
		desk_invoice.insert()
		self.assertEqual([a.reference_name for a in desk_invoice.advances], [advance])
		self.assertFalse(any("pulled as advance" in str(m) for m in frappe.message_log))
		desk_invoice.submit()
		self.assertAlmostEqual(
			desk_invoice.outstanding_amount,
			(desk_invoice.rounded_total or desk_invoice.grand_total) - 200,
			delta=0.02,
		)

		open_invoices = payments.customer_open_invoices(self.customer, self.company)
		self.assertGreaterEqual(len(open_invoices), 2)
		result = sales.register_payment(
			client_ref=ref(), customer=self.customer, payments=[{"mode_of_payment": "Cash", "amount": 50}]
		)
		entry = frappe.get_doc("Payment Entry", result["documents"][0]["name"])
		self.assertEqual([r.reference_name for r in entry.references], [open_invoices[0].name])
		self.assertEqual(entry.unallocated_amount, 0)

		old_advance = self._free_receipt(120)
		before = sum(t.open_amount for t in payments.customer_open_invoices(self.customer, self.company))
		links = customers.apply_customer_credit(self.customer)["links"]
		old_advance.reload()
		self.assertTrue(links)
		self.assertLess(old_advance.unallocated_amount, 0.01)
		after = sum(t.open_amount for t in payments.customer_open_invoices(self.customer, self.company))
		self.assertGreaterEqual(before - after, 119.99)
		self.assertEqual(frappe.db.get_value("Payment Entry", advance, "unallocated_amount"), 0)

		second_advance = self._free_receipt(75)
		result = self.sale(
			[{"item_code": "T-MIC", "qty": 1, "dims": {"production_year": "2025"}}],
			payments=[{"mode_of_payment": "Cash", "amount": 100}],
			deliver=1,
		)
		result = sales.invoice_order(client_ref=ref(), sales_order=result["order"]["name"])
		invoice = frappe.get_doc("Sales Invoice", first(result, "Sales Invoice"))
		second_advance.reload()
		self.assertLess(second_advance.unallocated_amount, 0.01, "free money goes to the oldest open invoice")
		self.assertEqual([round(a.allocated_amount) for a in invoice.advances], [100])

	def _free_receipt(self, amount):
		entry = frappe.get_doc(
			{
				"doctype": "Payment Entry",
				"payment_type": "Receive",
				"company": self.company,
				"party_type": "Customer",
				"party": self.customer,
				"mode_of_payment": "Cash",
				"paid_from": frappe.db.get_value("Company", self.company, "default_receivable_account"),
				"paid_to": context.payment_mode("Cash")["account"],
				"paid_amount": amount,
				"received_amount": amount,
				"reference_no": "X",
				"reference_date": nowdate(),
			}
		)
		entry.insert()
		entry.submit()
		return entry

	# ------------------------------------------------------------------ 9. money read model
	def test_90_paid_amounts_and_returns_in_totals(self):
		result = self.sale(
			[{"item_code": "T-MIC", "qty": 1, "dims": {"production_year": "2025"}}],
			payments=[{"mode_of_payment": "Cash", "amount": 100}],
		)
		order_name = result["order"]["name"]
		sales.deliver_order(client_ref=ref(), sales_order=order_name)
		result = sales.invoice_order(client_ref=ref(), sales_order=order_name)
		invoice = first(result, "Sales Invoice")
		self.assertAlmostEqual(
			result["order"]["paid"],
			100,
			delta=0.01,
			msg="advance pulled into the invoice is not counted twice",
		)
		result = sales.register_payment(
			client_ref=ref(),
			customer=self.customer,
			sales_order=order_name,
			payments=[{"mode_of_payment": "Cash", "amount": 100}],
		)
		self.assertEqual(
			frappe.get_all(
				"Payment Entry Reference",
				filters={"parent": result["documents"][0]["name"]},
				pluck="reference_name",
			),
			[invoice],
		)
		self.assertAlmostEqual(result["order"]["paid"], 200, delta=0.01)

		result = self.sale([{"item_code": "T-MIC", "qty": 2, "dims": {"production_year": "2025"}}])
		order_name, line = result["order"]["name"], result["order"]["lines"][0]
		sales.deliver_order(
			client_ref=ref(),
			sales_order=order_name,
			payments=[{"mode_of_payment": "Cash", "amount": result["order"]["total"]}],
		)
		result = sales.return_items(
			client_ref=ref(), sales_order=order_name, quantities={line["so_detail"]: 1}
		)
		self.assertAlmostEqual(
			result["order"]["total"], 460, delta=0.02, msg="goods returned before invoicing leave the total"
		)
		self.assertEqual(result["order"]["status"]["delivery"], "done")
		result = sales.invoice_order(client_ref=ref(), sales_order=order_name)
		self.assertTrue(
			all(result["order"]["status"][k] == "done" for k in ("payment", "invoice", "delivery"))
		)
		self.assertNotIn(
			order_name, [o["name"] for o in orders.list_orders(self.customer, only_incomplete=1)]
		)

		for target in payments.customer_open_invoices(self.customer, self.company):
			sales.register_payment(
				client_ref=ref(),
				customer=self.customer,
				payments=[{"mode_of_payment": "Cash", "amount": target.open_amount}],
			)
		result = self.sale([{"item_code": "T-MIC", "qty": 1, "dims": {"production_year": "2025"}}], deliver=1)
		order_name, line = result["order"]["name"], result["order"]["lines"][0]
		sales.invoice_order(
			client_ref=ref(), sales_order=order_name, payments=[{"mode_of_payment": "Cash", "amount": 460}]
		)
		credit_before = customers.get_customer(self.customer)["advance"]
		result = sales.return_items(
			client_ref=ref(), sales_order=order_name, quantities={line["so_detail"]: 1}
		)
		order = result["order"]
		self.assertAlmostEqual(order["total"], 0, delta=0.01)
		self.assertAlmostEqual(order["refund_due"], 460, delta=0.02)
		self.assertAlmostEqual(order["returns_value"], 460, delta=0.02)
		self.assertGreaterEqual(result["customer"]["advance"] - credit_before, 459.99)

		self.sale([{"item_code": "T-MIC", "qty": 1, "dims": {"production_year": "2025"}}])
		open_orders = payments.customer_open_orders(self.customer, self.company)
		result = sales.register_payment(
			client_ref=ref(), customer=self.customer, payments=[{"mode_of_payment": "Cash", "amount": 50}]
		)
		entry = frappe.get_doc("Payment Entry", result["documents"][0]["name"])
		self.assertEqual(
			(entry.references[0].reference_doctype, entry.references[0].reference_name),
			("Sales Order", open_orders[0].name),
		)
		self.assertLess(entry.unallocated_amount, 0.01)

	# ------------------------------------------------------------------ order list
	def test_95_order_list_and_filter(self):
		every = orders.list_orders(self.customer)
		incomplete = [o["name"] for o in orders.list_orders(self.customer, only_incomplete=1)]
		self.assertGreaterEqual(len(every), 4)
		self.assertNotIn(self.state["order1"], incomplete)
		self.assertIn(self.state["order4"], incomplete)

	# ------------------------------------------------------------------ duplicate protection
	def test_96_duplicate_protection(self):
		client_ref = ref()
		calls = []

		def failing():
			calls.append(1)
			raise frappe.ValidationError("boom")

		with self.assertRaises(frappe.ValidationError):
			idempotency.run_once(client_ref, failing)
		self.assertEqual(
			idempotency.run_once(client_ref, lambda: {"ok": True}),
			{"ok": True},
			"a failed action can be retried",
		)

		lines = [{"item_code": "T-VAL", "qty": 1, "dims": {"production_year": "2025"}}]
		client_ref = ref()
		first_result = self.sale(lines, client_ref=client_ref)
		frappe.cache.delete(idempotency._keys(client_ref)[0])  # e.g. Redis flushed
		count = frappe.db.count("Sales Order", {"customer": self.customer})
		again = self.sale(lines, client_ref=client_ref)
		self.assertEqual(again["order"]["name"], first_result["order"]["name"])
		self.assertEqual(frappe.db.count("Sales Order", {"customer": self.customer}), count)

	# ------------------------------------------------------------------ permissions
	def test_97_permissions_and_preferences(self):
		self.assertFails(lambda: session.set_preference("lang", "fr"), "invalid")
		self.assertFails(lambda: session.set_preference("color", "x"), "unknown")
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": "ksa-pos-viewer@example.com",
				"first_name": "Viewer",
				"send_welcome_email": 0,
				"roles": [{"role": "Stock User"}],
			}
		).insert(ignore_permissions=True)
		frappe.set_user(user.name)
		from ksa_retail.pos.permissions import has_app_permission

		self.assertFalse(has_app_permission())
		for call in (
			lambda: self.sale([{"item_code": "T-VAL", "qty": 1, "dims": {"production_year": "2025"}}]),
			lambda: customers.search_customers("a"),
			lambda: catalog.quote_sale(self.customer, [{"item_code": "T-VAL", "qty": 1}]),
			lambda: orders.list_orders(self.customer),
		):
			self.assertFails(call, "not permitted")

	# ------------------------------------------------------------------ warehouse choice
	def test_98_warehouse_choice(self):
		permitted = context.permitted_warehouses(self.company)
		self.assertIn(self.warehouse, permitted, "unrestricted users see every warehouse of the company")
		other = next(name for name in permitted if name != self.warehouse)

		session.set_preference("warehouse", other)
		context.clear_cache()
		self.assertEqual(context.get_context().warehouse, other)
		mic = next(i for i in catalog.search_items("T-MIC")["items"] if i.item_code == "T-MIC")
		self.assertEqual(mic.stock, [], "stock is shown for the selected warehouse")
		self.assertFails(
			lambda: self.sale([{"item_code": "T-MIC", "qty": 1, "dims": {"production_year": "2025"}}]),
			"available",
		)

		session.set_preference("warehouse", self.warehouse)
		context.clear_cache()
		self.assertEqual(context.get_context().warehouse, self.warehouse)

		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": "ksa-pos-branch@example.com",
				"first_name": "Branch",
				"send_welcome_email": 0,
				"roles": [{"role": "Sales User"}, {"role": "Stock User"}],
			}
		).insert(ignore_permissions=True)
		frappe.get_doc(
			{
				"doctype": "User Permission",
				"user": user.name,
				"allow": "Warehouse",
				"for_value": self.warehouse,
				"is_default": 1,
			}
		).insert(ignore_permissions=True)
		frappe.set_user(user.name)
		context.clear_cache()
		self.assertEqual(context.permitted_warehouses(self.company), [self.warehouse])
		self.assertEqual(context.get_context().warehouse, self.warehouse)
		self.assertFails(lambda: session.set_preference("warehouse", other), "not permitted")
		frappe.set_user("Administrator")
		context.clear_cache()

	# ------------------------------------------------------------------ order made before VAT existed
	def test_99_order_without_vat_invoiced_with_vat(self):
		template = context.get_context().tax_template
		frappe.db.set_value("Sales Taxes and Charges Template", template, "is_default", 0)
		context.clear_cache()
		self.assertIsNone(context.get_context().tax_template)
		result = self.sale([{"item_code": "T-MIC", "qty": 2, "dims": {"production_year": "2025"}}], deliver=1)
		order_name, line = result["order"]["name"], result["order"]["lines"][0]
		self.assertAlmostEqual(result["order"]["total"], 800, delta=0.01, msg="no VAT on the order")

		frappe.db.set_value("Sales Taxes and Charges Template", template, "is_default", 1)
		context.clear_cache()
		sales.return_items(client_ref=ref(), sales_order=order_name, quantities={line["so_detail"]: 1})
		result = sales.invoice_order(
			client_ref=ref(), sales_order=order_name, payments=[{"mode_of_payment": "Cash", "amount": 460}]
		)
		invoice = frappe.get_doc("Sales Invoice", first(result, "Sales Invoice"))
		order = result["order"]
		self.assertAlmostEqual(invoice.grand_total, 460, delta=0.01, msg="VAT added on the invoice")
		self.assertAlmostEqual(order["total"], 460, delta=0.01, msg="order total follows what was invoiced")
		self.assertAlmostEqual(order["refund_due"], 0, delta=0.01, msg="no false refund")
		self.assertTrue(all(order["status"][k] == "done" for k in ("payment", "invoice", "delivery")))

		from erpnext.accounts.utils import get_balance_on

		card = customers.get_customer(self.customer)
		self.assertAlmostEqual(
			card["balance"],
			get_balance_on(party_type="Customer", party=self.customer, company=self.company),
			delta=0.01,
		)
