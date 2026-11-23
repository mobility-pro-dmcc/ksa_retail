"""Deliveries.

How each kind of order line is delivered (the way ERPNext links documents):
* supplier-delivered lines -> Purchase Order to the supplier (drop-ship), marked
  Delivered, then the supplier's Purchase Invoice (Update Stock off: the goods never
  enter our warehouse);
* lines invoiced before delivery (legacy orders) -> Delivery Note made from the invoice;
* everything else -> Delivery Note made from the Sales Order.
Quantities are always capped by what is really pending (returns excluded).
"""

import json

import frappe
from frappe import _
from frappe.utils import flt, nowdate

from ksa_retail.pos import dimensions, order_summary, stock
from ksa_retail.pos.context import require_warehouse

EPSILON = 1e-9


# --------------------------------------------------------------------------- shared helpers
def lock_order(order_name: str) -> None:
	"""Serialise concurrent actions on the same order."""
	frappe.db.sql("select name from `tabSales Order` where name = %s for update", order_name)


def check_open(order) -> None:
	if order.docstatus != 1:
		frappe.throw(_("Sales Order {0} is not submitted.").format(order.name))
	if order.status in ("Closed", "On Hold"):
		frappe.throw(_("Sales Order {0} is {1}.").format(order.name, _(order.status)))


def cap_lines(order_name: str, requested: dict | None, pending_field: str) -> dict[str, float]:
	"""Requested qty per line, never more than really pending. No request = everything pending."""
	progress = order_summary.line_progress([order_name])
	pending = {k: p[pending_field] for k, p in progress.items() if p[pending_field] > EPSILON}
	if not requested:
		return pending
	capped = {k: min(flt(q), pending.get(k, 0)) for k, q in requested.items()}
	return {k: q for k, q in capped.items() if q > EPSILON}


def limit_rows_to(doc, quantities: dict[str, float], used: dict[str, float]) -> None:
	"""Trim mapped rows to the qty chosen for each Sales Order line (shared `used` across docs)."""
	for row in list(doc.items):
		line = row.get("so_detail")
		left = quantities.get(line, 0) - used.get(line, 0)
		if left <= 0:
			doc.remove(row)
			continue
		if flt(row.qty) > left:
			row.qty = left
		used[line] = used.get(line, 0) + flt(row.qty)
	for idx, row in enumerate(doc.items, 1):
		row.idx = idx


# --------------------------------------------------------------------------- deliver
def deliver_order(order_name: str, requested: dict | None = None, bill_no: str | None = None) -> list[tuple]:
	from erpnext.accounts.doctype.sales_invoice.sales_invoice import make_delivery_note as invoice_to_delivery
	from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note as order_to_delivery

	order = frappe.get_doc("Sales Order", order_name)
	check_open(order)
	quantities = cap_lines(order_name, requested, "pending_delivery")
	created: list[tuple] = []

	supplier_rows = [d for d in order.items if d.delivered_by_supplier and d.name in quantities]
	if supplier_rows:
		created += deliver_by_supplier(order, supplier_rows, bill_no)

	if not any(not d.delivered_by_supplier and d.name in quantities for d in order.items):
		if not created:
			frappe.throw(_("Everything on {0} is already delivered.").format(order_name))
		return created

	used: dict = {}
	# 1) legacy: invoiced before delivery -> deliver from the invoice (keeps SI <-> DN link)
	for invoice in _invoices_pending_delivery(order_name):
		delivery = invoice_to_delivery(invoice)
		delivery.items = [r for r in delivery.items if r.get("against_sales_order") == order_name]
		limit_rows_to(delivery, quantities, used)
		if delivery.items:
			created.append(_submit_delivery(delivery))

	# 2) the rest straight from the Sales Order
	order.reload()
	remaining = {k: v - used.get(k, 0) for k, v in quantities.items()}
	if any(v > 0 for v in remaining.values()):
		delivery = order_to_delivery(
			order_name, kwargs={"for_reserved_stock": False, "skip_item_mapping": False}
		)
		delivery.items = [r for r in delivery.items if not r.get("delivered_by_supplier")]
		limit_rows_to(delivery, quantities, used)
		if delivery.items:
			created.append(_submit_delivery(delivery))

	if not created:
		frappe.throw(_("Nothing selected to deliver."))
	return created


def _submit_delivery(delivery) -> tuple:
	warehouse = require_warehouse()
	for row in delivery.items:
		row.warehouse = row.warehouse or warehouse
	stock.validate_delivery_stock(delivery)
	stock.assign_batches(delivery)
	delivery.insert()
	delivery.submit()
	return ("Delivery Note", delivery.name)


def _invoices_pending_delivery(order_name: str) -> list[str]:
	return frappe.db.sql_list(
		"""select distinct si.name from `tabSales Invoice` si
		join `tabSales Invoice Item` sii on sii.parent = si.name
		where si.docstatus = 1 and si.is_return = 0 and ifnull(si.update_stock, 0) = 0
			and sii.sales_order = %s and ifnull(sii.dn_detail, '') = ''
			and ifnull(sii.delivered_by_supplier, 0) = 0 and sii.delivered_qty < sii.qty
		order by si.creation""",
		order_name,
	)


# --------------------------------------------------------------------------- supplier-direct
def deliver_by_supplier(order, rows, bill_no: str | None = None) -> list[tuple]:
	"""Drop-ship: Purchase Order -> status Delivered (updates the Sales Order's delivered qty,
	standard ERPNext behaviour) -> supplier's Purchase Invoice when its number is known."""
	from erpnext.buying.doctype.purchase_order.purchase_order import update_status

	frappe.has_permission("Purchase Order", "submit", throw=True)
	created: list[tuple] = []
	purchase_orders = frappe.db.sql_list(
		"""select distinct po.name from `tabPurchase Order` po
		join `tabPurchase Order Item` poi on poi.parent = po.name
		where poi.sales_order = %s and po.docstatus = 1 and poi.delivered_by_supplier = 1
			and po.status not in ('Delivered', 'Closed', 'Completed')""",
		order.name,
	)

	to_order = [d for d in rows if flt(d.ordered_qty) < flt(d.stock_qty)]
	if to_order:
		selected = [
			{
				"item_code": d.item_code,
				"name": d.name,
				"supplier": d.supplier,
				"pending_qty": flt(d.stock_qty) - flt(d.ordered_qty),
			}
			for d in to_order
		]
		for purchase_order in _purchase_orders_per_supplier(order.name, selected):
			if isinstance(purchase_order, str):
				purchase_order = frappe.get_doc("Purchase Order", purchase_order)
			_submit_purchase_order(purchase_order)
			purchase_orders.append(purchase_order.name)
			created.append(("Purchase Order", purchase_order.name))

	for name in purchase_orders:
		update_status("Delivered", name)
	# When this site requires the supplier's invoice number and it isn't known yet, the
	# order shows "Bill supplier" instead.
	if bill_no or not bill_no_required():
		created += bill_supplier_deliveries(order.name, bill_no)
	return created


def _purchase_orders_per_supplier(order_name: str, selected: list[dict]) -> list:
	"""One Purchase Order per supplier for the selected Sales Order lines.

	ERPNext v15 names this `make_purchase_order_for_default_supplier`; v16 folded it into
	`make_purchase_order` (same contract: list of inserted Purchase Orders). v15's own
	`make_purchase_order` is a different, single-document mapper, so check for v15 first."""
	from erpnext.selling.doctype.sales_order import sales_order

	factory = (
		getattr(sales_order, "make_purchase_order_for_default_supplier", None)
		or sales_order.make_purchase_order
	)
	result = factory(order_name, json.dumps(selected))
	if not result:
		return []
	return result if isinstance(result, list) else [result]


def _submit_purchase_order(purchase_order) -> None:
	purchase_order.schedule_date = purchase_order.schedule_date or nowdate()
	for row in purchase_order.items:
		row.schedule_date = row.schedule_date or nowdate()
	if purchase_order.docstatus == 0 and not purchase_order.get("taxes"):
		set_purchase_taxes(purchase_order)
	if purchase_order.is_new():
		purchase_order.insert()
	elif purchase_order.docstatus == 0:
		purchase_order.save()
	if purchase_order.docstatus == 0:
		purchase_order.submit()


def bill_no_required() -> bool:
	field = frappe.get_meta("Purchase Invoice").get_field("bill_no")
	return bool(field and field.reqd)


def purchase_tax_template(company: str, current: str | None = None) -> str | None:
	if current:
		return current
	default = frappe.db.get_value(
		"Purchase Taxes and Charges Template", {"company": company, "is_default": 1, "disabled": 0}
	)
	if default:
		return default
	templates = frappe.get_all(
		"Purchase Taxes and Charges Template", filters={"company": company, "disabled": 0}, pluck="name"
	)
	return templates[0] if len(templates) == 1 else None


def set_purchase_taxes(doc) -> None:
	template = purchase_tax_template(doc.company, doc.get("taxes_and_charges"))
	if template:
		doc.taxes_and_charges = template
		doc.set("taxes", [])
		doc.append_taxes_from_master()
		doc.calculate_taxes_and_totals()
	elif doc.meta.get_field("taxes").reqd:
		frappe.throw(
			_(
				"{0} needs taxes on this site, but there is no Purchase Taxes and Charges Template for {1}. "
				"Create one (e.g. VAT 15%) and tick Default."
			).format(_(doc.doctype), doc.company),
			title=_("Tax Template Missing"),
		)


def bill_supplier_deliveries(order_name: str, bill_no: str | None = None) -> list[tuple]:
	"""Purchase Invoice for each supplier-delivered, not fully billed Purchase Order of this
	order. Dimension values come from the Sales Order lines."""
	from erpnext.buying.doctype.purchase_order.purchase_order import make_purchase_invoice

	unbilled = frappe.db.sql_list(
		"""select distinct po.name from `tabPurchase Order` po
		join `tabPurchase Order Item` poi on poi.parent = po.name
		where poi.sales_order = %s and poi.delivered_by_supplier = 1 and po.docstatus = 1
			and po.status = 'Delivered' and po.per_billed < 99.99
		order by po.creation""",
		order_name,
	)
	if not unbilled:
		return []
	frappe.has_permission("Purchase Invoice", "submit", throw=True)
	if not bill_no and bill_no_required():
		frappe.throw(_("Enter the supplier's invoice number."), title=_("Missing Value"))

	dims = dimensions.order_line_dimensions()
	order_line_values = _order_line_dimension_values(order_name, dims)
	created = []
	for purchase_order in unbilled:
		invoice = make_purchase_invoice(purchase_order)
		invoice.update_stock = 0  # drop-ship: no stock movement in our books
		invoice.set_posting_time = 0
		invoice.posting_date = nowdate()
		invoice.bill_no = bill_no or invoice.get("bill_no")
		invoice.bill_date = nowdate() if invoice.bill_no else None
		for row in invoice.items:
			values = order_line_values.get(row.get("po_detail")) or {}
			for dimension in dims:
				if not row.get(dimension.source) and values.get(dimension.source):
					row.set(dimension.source, values[dimension.source])
		if not invoice.get("taxes"):
			set_purchase_taxes(invoice)
		invoice.insert()
		invoice.submit()
		created.append(("Purchase Invoice", invoice.name))
	return created


def _order_line_dimension_values(order_name: str, dims) -> dict[str, dict]:
	"""{Purchase Order Item: {dimension: value}} via the linked Sales Order lines (one query)."""
	if not dims:
		return {}
	columns = ", ".join(f"soi.`{d.source}`" for d in dims)
	rows = frappe.db.sql(
		f"""select poi.name as po_detail, {columns}
		from `tabPurchase Order Item` poi
		join `tabSales Order Item` soi on soi.name = poi.sales_order_item
		where poi.sales_order = %s""",
		order_name,
		as_dict=True,
	)
	return {r.po_detail: {d.source: r.get(d.source) for d in dims} for r in rows}
