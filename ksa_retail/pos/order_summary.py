"""Read model of POS orders: progress per line, money, status, cards and detail.

All functions take *lists* of orders and use a fixed number of queries per call
(no per-order or per-line queries).

Business rules encoded here
---------------------------
* Delivered / invoiced quantities are read from the submitted documents, net of returns.
* Returned quantity is no longer pending: an order with a return is not "incomplete".
* Only delivered quantity can be invoiced (supplier-delivered lines: the supplier's delivery).
* Paid = advances still on the order + paid part of its invoices - credit notes already
  settled (refunded or applied). Invoices spanning several orders are prorated by value.
* Order total = order grand total - credit notes - value of goods taken back before they
  were invoiced. Paying more than that total shows as "refund due".
"""

import frappe
from frappe import _
from frappe.utils import cint, cstr, flt

from ksa_retail.pos import dimensions, pricing

EPSILON = 1e-9
MONEY_EPSILON = 0.01
CARD_LINE_PREVIEW = 3
ORDER_FIELDS = [
	"name", "net_total", "transaction_date", "customer", "grand_total", "rounded_total",
	"advance_paid", "per_delivered", "per_billed", "status", "currency", "discount_amount", "docstatus",
]  # fmt: skip
INACTIVE_STATUSES = ("Closed", "On Hold", "Cancelled")


# --------------------------------------------------------------------------- pure rules
def derive_status(total: float, paid: float, per_billed: float, per_delivered: float) -> dict:
	def stage(percent):
		percent = flt(percent)
		return "done" if percent >= 99.99 else ("part" if percent > 0 else "pending")

	return {
		"payment": "done"
		if paid >= total - MONEY_EPSILON
		else ("part" if paid > MONEY_EPSILON else "pending"),
		"payment_pct": min(100, flt(paid / total * 100, 1)) if total else 0,
		"invoice": stage(per_billed),
		"invoice_pct": flt(per_billed, 1),
		"delivery": stage(per_delivered),
		"delivery_pct": flt(per_delivered, 1),
	}


def is_complete(status: dict) -> bool:
	return status["payment"] == status["invoice"] == status["delivery"] == "done"


def finish_line_progress(line: frappe._dict) -> frappe._dict:
	"""Derived quantities of one order line from its raw delivered / invoiced / returned sums."""
	line.net_dn = line.dn_out - line.dn_ret
	line.net_si = line.si_out - line.si_ret
	line.returned = max(line.dn_ret, line.si_ret)
	line.effective = max(line.qty - line.returned, 0)
	line.pending_delivery = max(line.effective - line.net_dn, 0)
	line.pending_billing = max(min(line.net_dn, line.effective) - line.net_si, 0)
	line.returnable = max(line.net_dn, line.net_si)
	return line


def order_percentages(lines: list[frappe._dict]) -> tuple[float, float]:
	"""(% delivered, % invoiced) of the quantity the customer keeps."""
	effective = sum(line.effective for line in lines)
	if not effective:
		return 100.0, 100.0
	delivered = sum(min(line.net_dn, line.effective) for line in lines)
	invoiced = sum(min(line.net_si, line.effective) for line in lines)
	return delivered / effective * 100, invoiced / effective * 100


def order_total(order) -> float:
	return flt(order.get("rounded_total")) or flt(order.get("grand_total"))


# --------------------------------------------------------------------------- batched reads
def invoices_for_orders(order_names) -> list[frappe._dict]:
	if not order_names:
		return []
	return frappe.db.sql(
		"""select sii.sales_order, si.name, si.grand_total, si.rounded_total, si.outstanding_amount,
			si.is_return, sum(sii.net_amount) as order_net, si.net_total
		from `tabSales Invoice Item` sii join `tabSales Invoice` si on si.name = sii.parent
		where si.docstatus = 1 and sii.sales_order in %s
		group by sii.sales_order, si.name""",
		(tuple(order_names),),
		as_dict=True,
	)


def order_advances(order_names) -> dict[str, float]:
	"""Money still sitting on each order as advance = submitted Payment Entry reference rows
	pointing at it. ERPNext moves those rows to the invoice when the advance is used, so
	this never double counts (Sales Order.advance_paid can be stale)."""
	if not order_names:
		return {}
	return {
		name: flt(amount)
		for name, amount in frappe.db.sql(
			"""select per.reference_name, sum(per.allocated_amount)
			from `tabPayment Entry Reference` per join `tabPayment Entry` pe on pe.name = per.parent
			where pe.docstatus = 1 and per.reference_doctype = 'Sales Order' and per.reference_name in %s
			group by per.reference_name""",
			(tuple(order_names),),
		)
	}


def line_progress(order_names) -> dict[str, frappe._dict]:
	"""{Sales Order Item: progress} for the given orders (three queries in total)."""
	if not order_names:
		return {}
	names = tuple(order_names)
	progress = {}
	for row in frappe.get_all(
		"Sales Order Item",
		filters={"parent": ["in", list(names)]},
		fields=["name", "parent", "qty", "delivered_qty", "delivered_by_supplier", "net_amount", "idx"],
	):
		progress[row.name] = frappe._dict(
			parent=row.parent,
			qty=flt(row.qty),
			net_amount=flt(row.net_amount),
			drop=cint(row.delivered_by_supplier),
			# supplier-delivered lines have no Delivery Note: the supplier's delivery counts
			dn_out=flt(row.delivered_qty) if row.delivered_by_supplier else 0.0,
			dn_ret=0.0,
			si_out=0.0,
			si_ret=0.0,
		)
	for so_detail, is_return, qty in frappe.db.sql(
		"""select dni.so_detail, dn.is_return, sum(dni.qty) from `tabDelivery Note Item` dni
		join `tabDelivery Note` dn on dn.name = dni.parent
		where dn.docstatus = 1 and dni.against_sales_order in %s group by dni.so_detail, dn.is_return""",
		(names,),
	):
		if so_detail in progress:
			progress[so_detail]["dn_ret" if is_return else "dn_out"] += abs(flt(qty))
	for so_detail, is_return, qty in frappe.db.sql(
		"""select sii.so_detail, si.is_return, sum(sii.qty) from `tabSales Invoice Item` sii
		join `tabSales Invoice` si on si.name = sii.parent
		where si.docstatus = 1 and sii.sales_order in %s group by sii.so_detail, si.is_return""",
		(names,),
	):
		if so_detail in progress:
			progress[so_detail]["si_ret" if is_return else "si_out"] += abs(flt(qty))
	for line in progress.values():
		finish_line_progress(line)
	return progress


def lines_by_order(progress: dict) -> dict[str, list]:
	grouped: dict = {}
	for line in progress.values():
		grouped.setdefault(line.parent, []).append(line)
	return grouped


def money(orders, progress: dict) -> dict[str, frappe._dict]:
	"""{order: {total, paid, credit, returned_value, refund_due, outstanding, ...}}

	total = what was invoiced (net of credit notes) + the value of what the customer keeps
	        but is not invoiced yet (order rates). Built from the invoices, so VAT added on
	        an invoice (orders made before a tax template existed) is counted correctly.
	paid  = advances still on the order + paid part of its invoices - settled credit notes.
	Invoices spanning several orders are prorated by line value."""
	names = [o.name for o in orders]
	advances = order_advances(names)
	paid = {n: advances.get(n, 0.0) for n in names}
	credit = {n: 0.0 for n in names}
	invoiced = {n: 0.0 for n in names}
	for inv in invoices_for_orders(names):
		share = flt(inv.order_net) / flt(inv.net_total) if flt(inv.net_total) else 1
		total = abs(order_total(inv))
		outstanding = abs(flt(inv.outstanding_amount))
		if inv.is_return:
			paid[inv.sales_order] -= (total - outstanding) * share
			credit[inv.sales_order] += total * share
		else:
			paid[inv.sales_order] += (total - outstanding) * share
			invoiced[inv.sales_order] += total * share

	grouped = lines_by_order(progress)
	result = {}
	for order in orders:
		# value of one unit at the order's rate, tax included as on the order
		ratio = order_total(order) / flt(order.net_total) if flt(order.net_total) else 1
		lines = [line for line in grouped.get(order.name, []) if line.qty]
		unit = {id(line): line.net_amount / line.qty * ratio for line in lines}
		not_invoiced = sum(max(line.effective - line.net_si, 0) * unit[id(line)] for line in lines)
		# goods taken back before they were invoiced: no credit note exists for them
		returned_uncredited = sum(max(line.dn_ret - line.si_ret, 0) * unit[id(line)] for line in lines)
		total = max(invoiced[order.name] - credit[order.name] + not_invoiced, 0)
		returns = credit[order.name] + returned_uncredited
		result[order.name] = frappe._dict(
			gross_total=total + returns,
			total=total,
			paid_raw=paid[order.name],
			paid=min(paid[order.name], total),
			credit=credit[order.name],
			returned_value=returns,
			not_invoiced=not_invoiced,
			advance=advances.get(order.name, 0.0),
			invoiced_total=invoiced[order.name],
			outstanding=max(0.0, total - paid[order.name]),
			refund_due=max(0.0, paid[order.name] - total),
		)
	return result


def open_amounts(orders) -> dict[str, float]:
	"""Part of each order that is neither invoiced nor already paid as advance (returns
	excluded), capped by ERPNext's own limit for a Payment Entry against a Sales Order."""
	candidates = [
		o
		for o in orders
		if o.docstatus == 1 and flt(o.per_billed) < 99.99 and o.status not in INACTIVE_STATUSES
	]
	if not candidates:
		return {}
	figures = money(candidates, line_progress([o.name for o in candidates]))
	amounts = {}
	for order in candidates:
		f = figures[order.name]
		open_amount = f.not_invoiced - f.advance
		erpnext_limit = order_total(order) - flt(order.advance_paid)
		amounts[order.name] = max(0.0, min(open_amount, erpnext_limit))
	return amounts


# --------------------------------------------------------------------------- edit rule
def order_invoices(order_name: str) -> list[str]:
	"""Any Sales Invoice (draft or submitted) made from this order."""
	return frappe.db.sql_list(
		"""select distinct si.name from `tabSales Invoice` si
		join `tabSales Invoice Item` sii on sii.parent = si.name
		where sii.sales_order = %s and si.docstatus < 2""",
		order_name,
	)


def edit_block_reason(order) -> str | None:
	"""Orders can be edited until any invoice exists (then: returns / credit notes)."""
	if flt(order.per_billed) > 0 or order_invoices(order.name):
		return _("{0} already has an invoice. Use a return / credit note instead of editing.").format(
			order.name
		)
	if order.docstatus != 1 or order.status in (*INACTIVE_STATUSES, "Completed"):
		return _("Sales Order {0} is {1}.").format(order.name, _(order.status))
	if any(d.delivered_by_supplier and flt(d.delivered_qty) > 0 for d in order.items):
		return _("{0} was delivered by the supplier and can no longer be edited.").format(order.name)
	return None


# --------------------------------------------------------------------------- cards
def list_orders(
	customer: str, only_incomplete: bool = False, start: int = 0, page_length: int = 20
) -> list[dict]:
	page_length = min(cint(page_length) or 20, 100)
	orders = frappe.get_list(
		"Sales Order",
		fields=ORDER_FIELDS,
		filters={"customer": customer, "docstatus": 1},
		order_by="transaction_date desc, creation desc",
		start=cint(start),
		# incomplete is derived from documents, so filter after computing (bounded scan)
		limit_page_length=200 if only_incomplete else page_length,
	)
	if not orders:
		return []

	names = [o.name for o in orders]
	progress = line_progress(names)
	figures = money(orders, progress)
	grouped = lines_by_order(progress)
	previews = _line_previews(names)

	cards = []
	for order in orders:
		f = figures[order.name]
		per_delivered, per_billed = order_percentages(grouped.get(order.name, []))
		status = derive_status(f.total, f.paid, per_billed, per_delivered)
		# returns never make an order "incomplete", and a closed order is finished
		if only_incomplete and (order.status == "Closed" or is_complete(status)):
			continue
		lines = previews.get(order.name, [])
		cards.append(
			{
				"name": order.name,
				"date": order.transaction_date,
				"status_label": order.status,
				"total": f.total,
				"paid": f.paid,
				"outstanding": f.outstanding,
				"refund_due": f.refund_due,
				"status": status,
				"drop_ship": any(line.delivered_by_supplier for line in lines),
				"item_count": len(lines),
				"items": [_brief(line) for line in lines[:CARD_LINE_PREVIEW]],
			}
		)
	return cards[:page_length] if only_incomplete else cards


def _line_previews(order_names) -> dict[str, list]:
	dims = dimensions.order_line_dimensions()
	grouped: dict = {}
	for row in frappe.get_all(
		"Sales Order Item",
		filters={"parent": ["in", order_names]},
		fields=[
			"parent",
			"item_code",
			"item_name",
			"qty",
			"idx",
			"delivered_by_supplier",
			*[d.source for d in dims],
		],
		order_by="idx asc",
	):
		row.dims = [cstr(row.get(d.source)) for d in dims if row.get(d.source)]
		grouped.setdefault(row.parent, []).append(row)
	return grouped


def _brief(line) -> dict:
	return {"item_code": line.item_code, "item_name": line.item_name, "qty": flt(line.qty), "dims": line.dims}


# --------------------------------------------------------------------------- detail
def order_detail(order) -> dict:
	"""Everything the checkout panel shows for one order."""
	progress = line_progress([order.name])
	f = money([order], progress)[order.name]
	per_delivered, per_billed = order_percentages(list(progress.values()))
	status = derive_status(f.total, f.paid, per_billed, per_delivered)
	active = order.status not in INACTIVE_STATUSES
	dims = dimensions.order_line_dimensions()
	linked = _linked_documents(order)

	lines = []
	for row in order.items:
		line = progress[row.name]
		lines.append(
			{
				"so_detail": row.name,
				"item_code": row.item_code,
				"item_name": row.item_name,
				"qty": flt(row.qty),
				"rate": flt(row.rate),
				"amount": flt(row.amount),
				"delivered_qty": line.net_dn,
				"billed_qty": line.net_si,
				"returned": line.returned,
				"pending_delivery": line.pending_delivery,
				"pending_billing": line.pending_billing,
				"returnable": line.returnable,
				"drop_ship": cint(row.delivered_by_supplier),
				"supplier": row.get("supplier"),
				"dims": {d.source: row.get(d.source) for d in dims},
			}
		)

	return {
		"name": order.name,
		"customer": order.customer,
		"customer_name": order.customer_name,
		"date": order.transaction_date,
		"status_label": order.status,
		"lines": lines,
		"totals": pricing.totals(order),
		"total": f.total,
		"gross_total": f.gross_total,
		"returns_value": f.returned_value,
		"paid": f.paid,
		"outstanding": f.outstanding,
		"refund_due": f.refund_due,
		"credit": f.credit,
		"status": status,
		"can_deliver": active and status["delivery"] != "done",
		"can_invoice": active and any(p.pending_billing > EPSILON for p in progress.values()),
		"can_return": order.docstatus == 1 and any(p.returnable > 0 for p in progress.values()),
		"drop_ship": any(line["drop_ship"] for line in lines),
		"edit_block": edit_block_reason(order),
		"supplier_unbilled": linked.pop("_supplier_unbilled"),
		"documents": linked,
	}


def _linked_documents(order) -> dict:
	delivery_notes = frappe.db.sql(
		"""select distinct dn.name, dn.posting_date, dn.status, dn.is_return, dn.creation
		from `tabDelivery Note` dn join `tabDelivery Note Item` dni on dni.parent = dn.name
		where dni.against_sales_order = %s and dn.docstatus = 1 order by dn.creation""",
		order.name,
		as_dict=True,
	)
	invoices = frappe.db.sql(
		"""select distinct si.name, si.posting_date, si.status, si.outstanding_amount, si.is_return,
			si.creation, si.grand_total, si.rounded_total
		from `tabSales Invoice` si join `tabSales Invoice Item` sii on sii.parent = si.name
		where sii.sales_order = %s and si.docstatus = 1 order by si.creation""",
		order.name,
		as_dict=True,
	)
	payments = frappe.db.sql(
		"""select distinct pe.name, pe.posting_date, pe.mode_of_payment, pe.paid_amount, pe.creation
		from `tabPayment Entry` pe join `tabPayment Entry Reference` per on per.parent = pe.name
		where pe.docstatus = 1 and per.reference_name in %s order by pe.creation""",
		(tuple([order.name] + [i.name for i in invoices]),),
		as_dict=True,
	)
	purchase_orders = frappe.db.sql(
		"""select distinct po.name, po.status, po.supplier, po.creation, po.per_billed
		from `tabPurchase Order` po join `tabPurchase Order Item` poi on poi.parent = po.name
		where poi.sales_order = %s and po.docstatus = 1 and poi.delivered_by_supplier = 1
		order by po.creation""",
		order.name,
		as_dict=True,
	)
	purchase_invoices = frappe.db.sql(
		"""select distinct pi.name, pi.posting_date, pi.status, pi.bill_no, pi.creation, pi.is_return
		from `tabPurchase Invoice` pi join `tabPurchase Invoice Item` pii on pii.parent = pi.name
		join `tabPurchase Order Item` poi on poi.name = pii.po_detail
		where poi.sales_order = %s and pi.docstatus = 1 order by pi.creation""",
		order.name,
		as_dict=True,
	)
	supplier_unbilled = any(po.status == "Delivered" and flt(po.per_billed) < 99.99 for po in purchase_orders)
	for po in purchase_orders:
		po.pop("per_billed", None)
	return {
		"Sales Order": [{"name": order.name, "creation": order.creation}],
		"Delivery Note": delivery_notes,
		"Sales Invoice": invoices,
		"Payment Entry": payments,
		"Purchase Order": purchase_orders,
		"Purchase Invoice": purchase_invoices,
		"_supplier_unbilled": supplier_unbilled,
	}
