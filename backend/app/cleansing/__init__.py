"""Ported cleansing/migration domain logic.

This package is where the pandas/sqlite logic from the original Streamlit
app's modules (address_cleansing_module.py, tax_cleansing_module.py, etc.)
is refactored into plain, UI-agnostic functions - callable from both API
routes and background jobs. Populated stage by stage starting in Phase 1c
(address cleansing first).
"""
