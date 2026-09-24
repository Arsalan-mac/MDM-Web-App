"""Seed data for the VAT_MAPPING table: which SAP TAXTYPE code the VAT
migration track assigns per country, extracted verbatim from
tax_cleansing_module.py::_VAT_MAPPING_SEED. Region only routed the
original's per-region export files (dropped here, see tax_service.py);
it's kept in the seed/model anyway since the Regelwerk-style editor lets
a user re-tag it, matching the original's editable table.

Russia (RU1/RU3) and Canada (CA1/CA2, chosen by pattern - see
_assign_ca_code in tax_service.py) are deliberately excluded from this
table's effect on migration: RU is always split into INN/KPP regardless
of any mapping row, and CA rows here are documentary only.
"""

VAT_MAPPING_SEED: list[dict[str, str]] = [
    {"Region": 'EU / Europe', "Code": 'AT0'},
    {"Region": 'EU / Europe', "Code": 'BE0'},
    {"Region": 'EU / Europe', "Code": 'BG0'},
    {"Region": 'EU / Europe', "Code": 'CY0'},
    {"Region": 'EU / Europe', "Code": 'CZ0'},
    {"Region": 'EU / Europe', "Code": 'DE0'},
    {"Region": 'EU / Europe', "Code": 'DK0'},
    {"Region": 'EU / Europe', "Code": 'EE0'},
    {"Region": 'EU / Europe', "Code": 'ES0'},
    {"Region": 'EU / Europe', "Code": 'FI0'},
    {"Region": 'EU / Europe', "Code": 'FR0'},
    {"Region": 'EU / Europe', "Code": 'GB0'},
    {"Region": 'EU / Europe', "Code": 'GR0'},
    {"Region": 'EU / Europe', "Code": 'HR0'},
    {"Region": 'EU / Europe', "Code": 'HU0'},
    {"Region": 'EU / Europe', "Code": 'IE0'},
    {"Region": 'EU / Europe', "Code": 'IM0'},
    {"Region": 'EU / Europe', "Code": 'IT0'},
    {"Region": 'EU / Europe', "Code": 'LT0'},
    {"Region": 'EU / Europe', "Code": 'LU0'},
    {"Region": 'EU / Europe', "Code": 'LV0'},
    {"Region": 'EU / Europe', "Code": 'MC0'},
    {"Region": 'EU / Europe', "Code": 'MK1'},
    {"Region": 'EU / Europe', "Code": 'MT0'},
    {"Region": 'EU / Europe', "Code": 'NL0'},
    {"Region": 'EU / Europe', "Code": 'NO1'},
    {"Region": 'EU / Europe', "Code": 'PL0'},
    {"Region": 'EU / Europe', "Code": 'PT0'},
    {"Region": 'EU / Europe', "Code": 'RO0'},
    {"Region": 'EU / Europe', "Code": 'SE0'},
    {"Region": 'EU / Europe', "Code": 'SI0'},
    {"Region": 'EU / Europe', "Code": 'SK0'},
    {"Region": 'EU / Europe', "Code": 'UA3'},
    {"Region": 'Non-EU', "Code": 'AE0'},
    {"Region": 'Non-EU', "Code": 'AU0'},
    {"Region": 'Non-EU', "Code": 'BA1'},
    {"Region": 'Non-EU', "Code": 'BH0'},
    {"Region": 'Non-EU', "Code": 'BW1'},
    {"Region": 'Non-EU', "Code": 'CA1'},
    {"Region": 'Non-EU', "Code": 'CA2'},
    {"Region": 'Non-EU', "Code": 'CH2'},
    {"Region": 'Non-EU', "Code": 'EC3'},
    {"Region": 'Non-EU', "Code": 'FJ3'},
    {"Region": 'Non-EU', "Code": 'ID3'},
    {"Region": 'Non-EU', "Code": 'IL0'},
    {"Region": 'Non-EU', "Code": 'IN3'},
    {"Region": 'Non-EU', "Code": 'KR2'},
    {"Region": 'Non-EU', "Code": 'KW0'},
    {"Region": 'Non-EU', "Code": 'MX1'},
    {"Region": 'Non-EU', "Code": 'MY1'},
    {"Region": 'Non-EU', "Code": 'NA1'},
    {"Region": 'Non-EU', "Code": 'NZ1'},
    {"Region": 'Non-EU', "Code": 'OM0'},
    {"Region": 'Non-EU', "Code": 'QA0'},
    {"Region": 'Non-EU', "Code": 'SA0'},
    {"Region": 'Non-EU', "Code": 'SG1'},
    {"Region": 'Non-EU', "Code": 'ZA1'},
    {"Region": 'Non-EU', "Code": 'ZW1'},
]
