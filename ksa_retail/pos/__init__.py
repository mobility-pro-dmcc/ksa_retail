"""KSA Retail point of sale.

Layout
------
api/             Whitelisted endpoints (thin: access check, input parsing, one service call).
inputs.py        Parsing / validation of request payloads into typed values.
context.py       Per-user selling context (company, warehouse, price list, payment modes).
dimensions.py    Inventory Dimension discovery (e.g. Production Year).
stock.py         Availability per item / warehouse / dimension, locking, batch picking.
catalog.py       Item search with prices and stock.
customers.py     Customer search, summary and registration.
pricing.py       Sales Order construction and totals (ERPNext does the maths).
order_summary.py Read model: order progress, money, status, cards and detail.
fulfilment.py    Deliveries (warehouse and supplier-direct) and supplier billing.
invoicing.py     Sales Invoices from delivered quantity, advance allocation.
payments.py      Receipts, refunds and credit reconciliation.
returns.py       Return Delivery Notes and credit notes.
order_editing.py Editing submitted, not-yet-invoiced orders.
transactions.py  Orchestration of the POS actions and their common result.
idempotency.py   Duplicate-submission protection tied to the DB transaction.
doc_events.py    Hooks that keep Desk-created documents consistent with POS rules.

Every write endpoint runs inside the single request transaction Frappe opens, so a
failure at any step rolls back all documents created by that action.
"""
