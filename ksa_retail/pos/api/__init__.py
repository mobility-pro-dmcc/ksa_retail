"""Whitelisted POS endpoints, grouped by area. See each module for its methods.

Conventions: every method passes `pos_endpoint` (POS access + POS language), parses its
input with `ksa_retail.pos.inputs`, and delegates to one service function. Write methods
are POST-only and take a `client_ref` used for duplicate protection.
"""
