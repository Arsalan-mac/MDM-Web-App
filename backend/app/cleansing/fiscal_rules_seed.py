"""Seed data for the FISCAL_RULES table: per-country, per-entity-type
(ORG/IND/GENERIC) tax-ID format rules, extracted verbatim from the
original app's tax_cleansing_module.py::_get_sap_fiscal_rules (research-
verified TIN formats, August 2025 - LOW-confidence entries are marked in
their description; verify at oecd.org/tax/.../tax-identification-numbers/).

Extracted programmatically (ast.literal_eval on the original function's
return value) rather than retyped by hand, to guarantee this reference
data - real tax-ID validation rules - carries over byte-for-byte.
"""

FISCAL_RULES_SEED: dict[str, dict[str, dict]] = {
    'AD': {
        'ORG': {'sap_code': 'AD3', 'regex': '^[A-Z]\\d{6}[A-Z]$', 'aliases': [], 'desc': 'NRT (Número de Registre Tributari)'},
        'IND': {'sap_code': 'AD3', 'regex': '^[A-Z]\\d{6}[A-Z]$', 'aliases': [], 'desc': 'NRT'},
        'GENERIC': {'sap_code': 'AD3', 'regex': '^[A-Z]\\d{6}[A-Z]$', 'aliases': [], 'desc': 'NRT'},
    },
    'AE': {
        'ORG': {'sap_code': 'AE1', 'regex': '^\\d{15}$', 'aliases': [], 'desc': 'TRN / VAT Registration (15 digits)'},
        'IND': {'sap_code': 'AE1', 'regex': '^784\\d{12}$', 'aliases': ['^\\d{15}$'], 'desc': 'Emirates ID (15 digits, starts 784)'},
        'GENERIC': {'sap_code': 'AE1', 'regex': '^\\d{15}$', 'aliases': [], 'desc': 'TRN or Emirates ID (15 digits)'},
    },
    'AF': {
        'ORG': {'sap_code': 'AF1', 'regex': '^\\d{9}$', 'aliases': ['^.+$'], 'desc': 'TIN (9 digits) [LOW confidence]'},
        'IND': {'sap_code': 'AF1', 'regex': '^\\d{9}$', 'aliases': ['^.+$'], 'desc': 'TIN (9 digits) [LOW confidence]'},
        'GENERIC': {'sap_code': 'AF1', 'regex': '^.+$', 'aliases': [], 'desc': 'TIN (variable) [LOW confidence]'},
    },
    'AO': {
        'ORG': {'sap_code': 'AO3', 'regex': '^\\d{9,10}$', 'aliases': [], 'desc': 'NIF (9-10 digits)'},
        'IND': {'sap_code': 'AO3', 'regex': '^\\d{9,10}$', 'aliases': [], 'desc': 'NIF (9-10 digits)'},
        'GENERIC': {'sap_code': 'AO3', 'regex': '^\\d{9,10}$', 'aliases': [], 'desc': 'NIF (9-10 digits)'},
    },
    'AR': {
        'ORG': {'sap_code': 'AR1A', 'regex': '^(30|33|34)\\d{9}$', 'aliases': ['^\\d{11}$'], 'desc': 'CUIT (11 digits, prefix 30/33/34 for companies)'},
        'IND': {'sap_code': 'AR1B', 'regex': '^(20|23|24|27)\\d{9}$', 'aliases': ['^\\d{11}$'], 'desc': 'CUIL (11 digits, prefix 20/23/24/27 for individuals)'},
        'GENERIC': {'sap_code': 'AR1C', 'regex': '^\\d{11}$', 'aliases': [], 'desc': 'CUIT/CUIL (11 digits)'},
    },
    'BE': {
        'ORG': {'sap_code': 'BE1', 'regex': '^\\d{10}$', 'aliases': ['^(BE)?0\\d{9}$'], 'desc': 'BTW/KBO Enterprise Number (10 digits; starts with 0)'},
        'IND': {'sap_code': 'BE2', 'regex': '^\\d{11}$', 'aliases': [], 'desc': 'Rijksregisternummer (11 digits)'},
        'GENERIC': {'sap_code': 'BE1', 'regex': '^\\d{10,11}$', 'aliases': [], 'desc': 'BTW/Enterprise (10) or Rijksnummer (11)'},
    },
    'BG': {
        'ORG': {'sap_code': 'BG1', 'regex': '^\\d{9}$', 'aliases': ['^\\d{13}$'], 'desc': 'EIK/UIC (9 digits; 13 for sub-entities)'},
        'IND': {'sap_code': 'BG2', 'regex': '^\\d{10}$', 'aliases': [], 'desc': 'EGN – civil number (10 digits)'},
        'GENERIC': {'sap_code': 'BG1', 'regex': '^\\d{9,10}$', 'aliases': ['^\\d{13}$'], 'desc': 'EIK or EGN'},
    },
    'BR': {
        'ORG': {'sap_code': 'BR1', 'regex': '^\\d{14}$', 'aliases': [], 'desc': 'CNPJ (14 digits)'},
        'IND': {'sap_code': 'BR2', 'regex': '^\\d{11}$', 'aliases': [], 'desc': 'CPF (11 digits)'},
        'GENERIC': {'sap_code': 'BR1', 'regex': '^\\d{11}$', 'aliases': ['^\\d{14}$'], 'desc': 'CPF (11) or CNPJ (14)'},
    },
    'BZ': {
        'ORG': {'sap_code': 'BZ5', 'regex': '^\\d{9,10}$', 'aliases': ['^.+$'], 'desc': 'TIN (9-10 digits) [LOW confidence]'},
        'IND': {'sap_code': 'BZ1', 'regex': '^\\d{9,10}$', 'aliases': ['^.+$'], 'desc': 'TIN (9-10 digits) [LOW confidence]'},
        'GENERIC': {'sap_code': 'BZ2', 'regex': '^.+$', 'aliases': [], 'desc': 'TIN (variable) [LOW confidence]'},
    },
    'CA': {
        'ORG': {'sap_code': 'CA2', 'regex': '^\\d{9}$', 'aliases': ['^\\d{9}[A-Z]{2}\\d{4}$'], 'desc': 'Business Number (9 digits; +account suffix for RT/RM etc.)'},
        'IND': {'sap_code': 'CA2', 'regex': '^\\d{9}$', 'aliases': [], 'desc': 'SIN (9 digits)'},
        'GENERIC': {'sap_code': 'CA2', 'regex': '^\\d{9}$', 'aliases': [], 'desc': 'BN or SIN (9 digits)'},
    },
    'CH': {
        'ORG': {'sap_code': 'CH1', 'regex': '^CHE\\d{9}$', 'aliases': ['^\\d{9}$'], 'desc': 'UID (CHE + 9 digits); alias: 9 digits only (CHE prefix omitted in source)'},
        'IND': {'sap_code': 'CH2', 'regex': '^756\\d{10}$', 'aliases': ['^\\d{10}$', '^\\d{13}$'], 'desc': 'AHV-Nummer (756 + 10 digits = 13 chars, dots stripped); alias: 10 digits only'},
        'GENERIC': {'sap_code': 'CH1', 'regex': '^(CHE\\d{9}|756\\d{10}|\\d{13})$', 'aliases': ['^\\d{9,13}$'], 'desc': 'UID or AHV-Nummer'},
    },
    'CI': {
        'ORG': {'sap_code': 'CI3', 'regex': '^[A-Z0-9]{7,8}$', 'aliases': ['^.+$'], 'desc': 'NCC (7-8 chars) [LOW confidence]'},
        'IND': {'sap_code': 'CI3', 'regex': '^[A-Z0-9]{7,8}$', 'aliases': ['^.+$'], 'desc': 'NCC (7-8 chars) [LOW confidence]'},
        'GENERIC': {'sap_code': 'CI3', 'regex': '^.+$', 'aliases': [], 'desc': 'NCC (variable) [LOW confidence]'},
    },
    'CL': {
        'ORG': {'sap_code': 'CL1', 'regex': '^\\d{7,9}[\\dK]$', 'aliases': [], 'desc': 'RUT (7-9 digits + checksum digit/K, hyphen stripped)'},
        'IND': {'sap_code': 'CL1', 'regex': '^\\d{7,9}[\\dK]$', 'aliases': [], 'desc': 'RUT (same format for individuals)'},
        'GENERIC': {'sap_code': 'CL1', 'regex': '^\\d{7,9}[\\dK]$', 'aliases': [], 'desc': 'RUT (8-10 chars after stripping hyphen)'},
    },
    'CM': {
        'ORG': {'sap_code': 'CM3', 'regex': '^M\\d{9}[A-Z]$', 'aliases': ['^.+$'], 'desc': 'NIU (M + 9 digits + letter) [LOW confidence]'},
        'IND': {'sap_code': 'CM3', 'regex': '^[MP]\\d{9}[A-Z]$', 'aliases': ['^.+$'], 'desc': 'NIU (P/M prefix) [LOW confidence]'},
        'GENERIC': {'sap_code': 'CM3', 'regex': '^.+$', 'aliases': [], 'desc': 'NIU (variable) [LOW confidence]'},
    },
    'CN': {
        'ORG': {'sap_code': 'CN0', 'regex': '^[0-9A-HJ-NP-RT-UWX-Y]{18}$', 'aliases': ['^[A-Z0-9]{15,18}$'], 'desc': 'USCC (18 chars, restricted charset)'},
        'IND': {'sap_code': 'CN0', 'regex': '^\\d{17}[\\dX]$', 'aliases': ['^[A-Z0-9]{18}$'], 'desc': 'Citizen ID (18 chars: 17 digits + digit/X)'},
        'GENERIC': {'sap_code': 'CN0', 'regex': '^[A-Z0-9]{15,18}$', 'aliases': [], 'desc': 'USCC or Citizen ID (15-18 chars)'},
    },
    'CO': {
        'ORG': {'sap_code': 'CO1', 'regex': '^\\d{9,10}$', 'aliases': ['^\\d{9,11}$'], 'desc': 'NIT (9-10 digits + optional check digit)'},
        'IND': {'sap_code': 'CO1', 'regex': '^\\d{6,10}$', 'aliases': [], 'desc': 'Cédula (6-10 digits)'},
        'GENERIC': {'sap_code': 'CO1', 'regex': '^\\d{6,11}$', 'aliases': [], 'desc': 'NIT or Cédula'},
    },
    'CR': {
        'ORG': {'sap_code': 'CR3', 'regex': '^\\d{10}$', 'aliases': [], 'desc': 'Cédula Jurídica (10 digits)'},
        'IND': {'sap_code': 'CR3', 'regex': '^\\d{9}$', 'aliases': [], 'desc': 'Cédula de Identidad (9 digits)'},
        'GENERIC': {'sap_code': 'CR3', 'regex': '^\\d{9,10}$', 'aliases': [], 'desc': 'Cédula Jurídica (10) or de Identidad (9)'},
    },
    'CW': {
        'ORG': {'sap_code': 'CW3', 'regex': '^\\d{9}$', 'aliases': ['^.+$'], 'desc': 'CRIB number (9 digits) [LOW confidence]'},
        'IND': {'sap_code': 'CW3', 'regex': '^\\d{9}$', 'aliases': ['^.+$'], 'desc': 'CRIB/A-number (9 digits) [LOW confidence]'},
        'GENERIC': {'sap_code': 'CW3', 'regex': '^\\d{9}$', 'aliases': [], 'desc': 'CRIB (9 digits) [LOW confidence]'},
    },
    'CZ': {
        'ORG': {'sap_code': 'CZ1', 'regex': '^\\d{8}$', 'aliases': [], 'desc': 'IČO (8 digits)'},
        'IND': {'sap_code': 'CZ2', 'regex': '^\\d{9,10}$', 'aliases': [], 'desc': 'Rodné číslo (9-10 digits, slash stripped)'},
        'GENERIC': {'sap_code': 'CZ1', 'regex': '^\\d{8,10}$', 'aliases': [], 'desc': 'IČO or Rodné číslo'},
    },
    'DE': {
        'ORG': {'sap_code': 'DE1', 'regex': '^\\d{10,11}$', 'aliases': ['^\\d{13}$'], 'desc': 'Steuernummer (10-11 Ziffern nach Entfernen der Schrägstriche; Bundesschema 13 Ziffern)'},
        'IND': {'sap_code': 'DE1', 'regex': '^\\d{10,11}$', 'aliases': ['^\\d{13}$'], 'desc': 'Steuernummer (10-11 Ziffern, auch führende Null erlaubt; Bundesschema 13 Ziffern)'},
        'GENERIC': {'sap_code': 'DE1', 'regex': '^\\d{10,11}$', 'aliases': ['^\\d{13}$'], 'desc': 'Steuernummer (10-11) oder Bundesschema (13)'},
    },
    'DK': {
        'ORG': {'sap_code': 'DK2', 'regex': '^\\d{8}$', 'aliases': [], 'desc': 'CVR-nummer (8 digits)'},
        'IND': {'sap_code': 'DK1', 'regex': '^\\d{10}$', 'aliases': [], 'desc': 'CPR-nummer (10 digits, hyphen stripped)'},
        'GENERIC': {'sap_code': 'DK2', 'regex': '^\\d{8,10}$', 'aliases': [], 'desc': 'CVR (8) or CPR (10)'},
    },
    'DZ': {
        'ORG': {'sap_code': 'DZ1', 'regex': '^\\d{15}$', 'aliases': [], 'desc': 'NIF (15 digits)'},
        'IND': {'sap_code': 'DZ1', 'regex': '^\\d{15}$', 'aliases': [], 'desc': 'NIF (15 digits)'},
        'GENERIC': {'sap_code': 'DZ1', 'regex': '^\\d{15}$', 'aliases': [], 'desc': 'NIF (15 digits)'},
    },
    'EG': {
        'ORG': {'sap_code': 'EG3', 'regex': '^\\d{9}$', 'aliases': [], 'desc': 'Tax Registration Number (9 digits)'},
        'IND': {'sap_code': 'EG3', 'regex': '^\\d{14}$', 'aliases': [], 'desc': 'National ID (14 digits)'},
        'GENERIC': {'sap_code': 'EG3', 'regex': '^\\d{9}$', 'aliases': ['^\\d{14}$'], 'desc': 'Tax Reg. (9) or National ID (14)'},
    },
    'ES': {
        'ORG': {'sap_code': 'ES5', 'regex': '^[A-HJNP-SW]\\d{7}[A-J0-9]$', 'aliases': ['^[A-Z0-9]{9}$'], 'desc': 'NIF (CIF) for entities (9 chars)'},
        'IND': {'sap_code': 'ES1', 'regex': '^\\d{8}[A-Z]$', 'aliases': ['^[XYZ]\\d{7}[A-Z]$'], 'desc': 'DNI (8 digits + letter) or NIE (X/Y/Z + 7 digits + letter)'},
        'GENERIC': {'sap_code': 'ES1', 'regex': '^[A-Z0-9]{9}$', 'aliases': [], 'desc': 'NIF/DNI/NIE (9 chars)'},
    },
    'FR': {
        'ORG': {'sap_code': 'FR3', 'regex': '^\\d{9}$', 'aliases': ['^\\d{14}$'], 'desc': 'SIREN (9 digits); SIRET (14 digits) accepted as alias'},
        'IND': {'sap_code': 'FR2', 'regex': '^\\d{13}$', 'aliases': [], 'desc': 'Numéro fiscal / SPI / NIF (13 digits)'},
        'GENERIC': {'sap_code': 'FR3', 'regex': '^\\d{9}$', 'aliases': ['^\\d{13}$', '^\\d{14}$'], 'desc': 'SIREN, SIRET or NIF'},
    },
    'GB': {
        'ORG': {'sap_code': 'GB3', 'regex': '^\\d{10}$', 'aliases': ['^\\d{8}$', '^[A-Z]{2}\\d{6}$'], 'desc': 'UTR (10 digits); CRN (8 digits or 2 letters+6 digits) as alias'},
        'IND': {'sap_code': 'GB4', 'regex': '^\\d{10}$', 'aliases': ['^[A-CEGHJ-PR-TW-Z]{2}\\d{6}[A-D]$'], 'desc': 'UTR (10 digits) or NINO (2 letters + 6 digits + letter)'},
        'GENERIC': {'sap_code': 'GB4', 'regex': '^\\d{10}$', 'aliases': ['^\\d{8}$', '^[A-Z0-9]{8,10}$'], 'desc': 'UTR, CRN or NINO'},
    },
    'GE': {
        'ORG': {'sap_code': 'GE3', 'regex': '^\\d{9}$', 'aliases': [], 'desc': 'Identification Number (9 digits)'},
        'IND': {'sap_code': 'GE3', 'regex': '^\\d{11}$', 'aliases': [], 'desc': 'Personal Number (11 digits)'},
        'GENERIC': {'sap_code': 'GE3', 'regex': '^\\d{9,11}$', 'aliases': [], 'desc': 'TIN (9 or 11 digits)'},
    },
    'GH': {
        'ORG': {'sap_code': 'GH1', 'regex': '^[CP]\\d{10}$', 'aliases': ['^[A-Z]\\d{10}$'], 'desc': 'KRA TIN (C/P + 10 digits)'},
        'IND': {'sap_code': 'GH1', 'regex': '^P\\d{10}$', 'aliases': ['^[A-Z]\\d{10}$'], 'desc': 'KRA TIN (P + 10 digits for persons)'},
        'GENERIC': {'sap_code': 'GH1', 'regex': '^[A-Z]\\d{10}$', 'aliases': [], 'desc': 'TIN (letter + 10 digits)'},
    },
    'GR': {
        'ORG': {'sap_code': 'GR2', 'regex': '^\\d{9}$', 'aliases': [], 'desc': 'AFM (9 digits)'},
        'IND': {'sap_code': 'GR1', 'regex': '^\\d{9}$', 'aliases': [], 'desc': 'AFM (9 digits)'},
        'GENERIC': {'sap_code': 'GR2', 'regex': '^\\d{9}$', 'aliases': [], 'desc': 'AFM (9 digits)'},
    },
    'HK': {
        'ORG': {'sap_code': 'HK3', 'regex': '^\\d{8}$', 'aliases': [], 'desc': 'Business Registration Number (8 digits)'},
        'IND': {'sap_code': 'HK3', 'regex': '^[A-Z]{1,2}\\d{6}[\\dA]$', 'aliases': [], 'desc': 'HKID-based (1-2 letters + 6 digits + checksum)'},
        'GENERIC': {'sap_code': 'HK3', 'regex': '^\\d{8}$', 'aliases': ['^[A-Z]{1,2}\\d{6}[\\dA]$'], 'desc': 'BRN (8 digits) or HKID'},
    },
    'HR': {
        'ORG': {'sap_code': 'HR2', 'regex': '^\\d{11}$', 'aliases': [], 'desc': 'OIB (11 digits)'},
        'IND': {'sap_code': 'HR1', 'regex': '^\\d{11}$', 'aliases': [], 'desc': 'OIB (11 digits)'},
        'GENERIC': {'sap_code': 'HR2', 'regex': '^\\d{11}$', 'aliases': [], 'desc': 'OIB (11 digits)'},
    },
    'HU': {
        'ORG': {'sap_code': 'HU1', 'regex': '^\\d{11}$', 'aliases': [], 'desc': 'Adószám (11 digits, separators stripped)'},
        'IND': {'sap_code': 'HU2', 'regex': '^8\\d{9}$', 'aliases': ['^\\d{10}$'], 'desc': 'Adóazonosító jel (10 digits, starts with 8)'},
        'GENERIC': {'sap_code': 'HU1', 'regex': '^\\d{10,11}$', 'aliases': [], 'desc': 'Adószám or Adóazonosító'},
    },
    'ID': {
        'ORG': {'sap_code': 'ID1', 'regex': '^\\d{15}$', 'aliases': ['^\\d{16}$'], 'desc': 'NPWP (15 digits); new 16-digit NIK-based in transition'},
        'IND': {'sap_code': 'ID1', 'regex': '^\\d{15}$', 'aliases': ['^\\d{16}$'], 'desc': 'NPWP (15 digits)'},
        'GENERIC': {'sap_code': 'ID1', 'regex': '^\\d{15,16}$', 'aliases': [], 'desc': 'NPWP (15-16 digits)'},
    },
    'IE': {
        'ORG': {'sap_code': 'IE1', 'regex': '^\\d{7}[A-Z]{1,2}$', 'aliases': [], 'desc': 'TAN/CHY (7 digits + 1-2 letters)'},
        'IND': {'sap_code': 'IE2', 'regex': '^\\d{7}[A-Z]{1,2}$', 'aliases': [], 'desc': 'PPSN (7 digits + 1-2 letters)'},
        'GENERIC': {'sap_code': 'IE1', 'regex': '^\\d{7}[A-Z]{1,2}$', 'aliases': [], 'desc': 'Irish TIN (7 + 1-2 chars)'},
    },
    'IL': {
        'ORG': {'sap_code': 'IL1', 'regex': '^\\d{9}$', 'aliases': [], 'desc': 'Company number (9 digits)'},
        'IND': {'sap_code': 'IL2', 'regex': '^\\d{9}$', 'aliases': [], 'desc': 'Teudat Zehut (9 digits)'},
        'GENERIC': {'sap_code': 'IL1', 'regex': '^\\d{9}$', 'aliases': [], 'desc': 'TIN (9 digits)'},
    },
    'IN': {
        'ORG': {'sap_code': 'IN2', 'regex': '^[A-Z]{5}\\d{4}[A-Z]$', 'aliases': [], 'desc': 'PAN (10 chars: AAAAA9999A; 4th char = C for companies)'},
        'IND': {'sap_code': 'IN2', 'regex': '^[A-Z]{3}P\\d{4}[A-Z]$', 'aliases': ['^[A-Z]{5}\\d{4}[A-Z]$'], 'desc': 'PAN for individuals (4th char = P)'},
        'GENERIC': {'sap_code': 'IN2', 'regex': '^[A-Z]{5}\\d{4}[A-Z]$', 'aliases': [], 'desc': 'PAN (10 alphanumeric)'},
    },
    'IR': {
        'ORG': {'sap_code': 'IR3', 'regex': '^\\d{11}$', 'aliases': [], 'desc': 'Shenase Melli (11 digits)'},
        'IND': {'sap_code': 'IR3', 'regex': '^\\d{10}$', 'aliases': [], 'desc': 'Code Melli (10 digits)'},
        'GENERIC': {'sap_code': 'IR3', 'regex': '^\\d{10,11}$', 'aliases': [], 'desc': 'Code Melli (10) or Shenase Melli (11)'},
    },
    'IS': {
        'ORG': {'sap_code': 'IS3', 'regex': '^\\d{10}$', 'aliases': [], 'desc': 'Kennitala (10 digits)'},
        'IND': {'sap_code': 'IS3', 'regex': '^\\d{10}$', 'aliases': [], 'desc': 'Kennitala (10 digits)'},
        'GENERIC': {'sap_code': 'IS3', 'regex': '^\\d{10}$', 'aliases': [], 'desc': 'Kennitala (10 digits)'},
    },
    'IT': {
        'ORG': {'sap_code': 'IT2', 'regex': '^\\d{11}$', 'aliases': [], 'desc': 'Partita IVA (11 digits)'},
        'IND': {'sap_code': 'IT1', 'regex': '^[A-Z]{6}\\d{2}[A-Z]\\d{2}[A-Z]\\d{3}[A-Z]$', 'aliases': ['^\\d{11}$'], 'desc': 'Codice Fiscale (16 chars); alias: Partita IVA (11 digits) for sole proprietors'},
        'GENERIC': {'sap_code': 'IT2', 'regex': '^\\d{11}$', 'aliases': ['^[A-Z]{6}\\d{2}[A-Z]\\d{2}[A-Z]\\d{3}[A-Z]$'], 'desc': 'Partita IVA or Codice Fiscale'},
    },
    'JO': {
        'ORG': {'sap_code': 'JO3', 'regex': '^\\d{9}$', 'aliases': ['^\\d{9,10}$'], 'desc': 'TIN (9 digits)'},
        'IND': {'sap_code': 'JO3', 'regex': '^\\d{9,10}$', 'aliases': [], 'desc': 'National ID / TIN (9-10 digits)'},
        'GENERIC': {'sap_code': 'JO3', 'regex': '^\\d{9,10}$', 'aliases': [], 'desc': 'TIN (9-10 digits)'},
    },
    'JP': {
        'ORG': {'sap_code': 'JP3', 'regex': '^\\d{13}$', 'aliases': [], 'desc': 'Corporate Number / 法人番号 (13 digits)'},
        'IND': {'sap_code': 'JP4', 'regex': '^\\d{12}$', 'aliases': [], 'desc': 'My Number / 個人番号 (12 digits)'},
        'GENERIC': {'sap_code': 'JP3', 'regex': '^\\d{12,13}$', 'aliases': [], 'desc': 'Corporate Number (13) or My Number (12)'},
    },
    'KE': {
        'ORG': {'sap_code': 'KE3', 'regex': '^P\\d{9}[A-Z]$', 'aliases': ['^[A-Z]\\d{9}[A-Z]$'], 'desc': 'KRA PIN (P + 9 digits + letter for companies)'},
        'IND': {'sap_code': 'KE3', 'regex': '^[A-Z]\\d{9}[A-Z]$', 'aliases': [], 'desc': 'KRA PIN (letter + 9 digits + letter)'},
        'GENERIC': {'sap_code': 'KE3', 'regex': '^[A-Z]\\d{9}[A-Z]$', 'aliases': [], 'desc': 'KRA PIN (11 chars)'},
    },
    'KP': {
        'ORG': {'sap_code': 'KP3', 'regex': '^.+$', 'aliases': [], 'desc': 'No documented format [NO DATA]'},
        'IND': {'sap_code': 'KP3', 'regex': '^.+$', 'aliases': [], 'desc': 'No documented format [NO DATA]'},
        'GENERIC': {'sap_code': 'KP3', 'regex': '^.+$', 'aliases': [], 'desc': 'No documented format [NO DATA]'},
    },
    'KR': {
        'ORG': {'sap_code': 'KR1', 'regex': '^\\d{10}$', 'aliases': [], 'desc': 'BRN / 사업자등록번호 (10 digits)'},
        'IND': {'sap_code': 'KR2', 'regex': '^\\d{13}$', 'aliases': [], 'desc': 'RRN / 주민등록번호 (13 digits)'},
        'GENERIC': {'sap_code': 'KR1', 'regex': '^\\d{10}$', 'aliases': ['^\\d{13}$'], 'desc': 'BRN (10) or RRN (13)'},
    },
    'KW': {
        'ORG': {'sap_code': 'KW1', 'regex': '^\\d{9,12}$', 'aliases': ['^.+$'], 'desc': 'Commercial Registration / TIN (9-12 digits) [LOW confidence]'},
        'IND': {'sap_code': 'KW1', 'regex': '^\\d{12}$', 'aliases': [], 'desc': 'Civil ID (12 digits)'},
        'GENERIC': {'sap_code': 'KW1', 'regex': '^\\d{9,12}$', 'aliases': [], 'desc': 'TIN or Civil ID'},
    },
    'KZ': {
        'ORG': {'sap_code': 'KZ3', 'regex': '^\\d{12}$', 'aliases': [], 'desc': 'BIN (12 digits)'},
        'IND': {'sap_code': 'KZ4', 'regex': '^\\d{12}$', 'aliases': [], 'desc': 'IIN (12 digits)'},
        'GENERIC': {'sap_code': 'KZ1', 'regex': '^\\d{12}$', 'aliases': [], 'desc': 'BIN or IIN (12 digits)'},
    },
    'LC': {
        'ORG': {'sap_code': 'LC3', 'regex': '^\\d{8,9}$', 'aliases': ['^.+$'], 'desc': 'TIN (8-9 digits) [LOW confidence]'},
        'IND': {'sap_code': 'LC3', 'regex': '^\\d{8,9}$', 'aliases': ['^.+$'], 'desc': 'TIN (8-9 digits) [LOW confidence]'},
        'GENERIC': {'sap_code': 'LC3', 'regex': '^\\d{8,9}$', 'aliases': [], 'desc': 'TIN [LOW confidence]'},
    },
    'MA': {
        'ORG': {'sap_code': 'MA3', 'regex': '^\\d{15}$', 'aliases': ['^\\d{8}$'], 'desc': 'ICE (15 digits) primary; IF (8 digits) as alias'},
        'IND': {'sap_code': 'MA3', 'regex': '^\\d{8,9}$', 'aliases': [], 'desc': 'IF (8-9 digits)'},
        'GENERIC': {'sap_code': 'MA3', 'regex': '^\\d{8,15}$', 'aliases': [], 'desc': 'ICE (15) or IF (8-9)'},
    },
    'MC': {
        'ORG': {'sap_code': 'MC1', 'regex': '^\\d{5,7}$', 'aliases': [], 'desc': 'RCI Registration (variable) [LOW confidence]'},
        'IND': {'sap_code': 'MC2', 'regex': '^\\d{13}$', 'aliases': ['^\\d{5,13}$'], 'desc': 'French-style NIF or Monegasque ID [LOW confidence]'},
        'GENERIC': {'sap_code': 'MC1', 'regex': '^\\d{5,13}$', 'aliases': [], 'desc': 'Monaco TIN (variable)'},
    },
    'MD': {
        'ORG': {'sap_code': 'MD1', 'regex': '^\\d{13}$', 'aliases': [], 'desc': 'IDNO (13 digits)'},
        'IND': {'sap_code': 'MD1', 'regex': '^\\d{13}$', 'aliases': [], 'desc': 'IDNP (13 digits)'},
        'GENERIC': {'sap_code': 'MD1', 'regex': '^\\d{13}$', 'aliases': [], 'desc': 'IDNO/IDNP (13 digits)'},
    },
    'MU': {
        'ORG': {'sap_code': 'MU1', 'regex': '^C\\d{7}$', 'aliases': ['^\\d{8}$'], 'desc': 'BRN (C + 7 digits)'},
        'IND': {'sap_code': 'MU1', 'regex': '^\\d{9}$', 'aliases': ['^.+$'], 'desc': 'NIC/TAN (9 digits) [MED confidence]'},
        'GENERIC': {'sap_code': 'MU1', 'regex': '^\\d{8,9}$', 'aliases': ['^C\\d{7}$'], 'desc': 'BRN or NIC'},
    },
    'MV': {
        'ORG': {'sap_code': 'MV3', 'regex': '^\\d{7}[A-Z]?$', 'aliases': ['^.+$'], 'desc': 'BRN/TIN (7 digits + optional letter) [LOW confidence]'},
        'IND': {'sap_code': 'MV3', 'regex': '^\\d{7,9}$', 'aliases': ['^.+$'], 'desc': 'NIN (7-9 digits) [LOW confidence]'},
        'GENERIC': {'sap_code': 'MV3', 'regex': '^.+$', 'aliases': [], 'desc': 'TIN (variable) [LOW confidence]'},
    },
    'MW': {
        'ORG': {'sap_code': 'MW1', 'regex': '^\\d{9}$', 'aliases': ['^.+$'], 'desc': 'TIN (9 digits) [LOW confidence]'},
        'IND': {'sap_code': 'MW1', 'regex': '^\\d{9}$', 'aliases': ['^.+$'], 'desc': 'TIN (9 digits) [LOW confidence]'},
        'GENERIC': {'sap_code': 'MW1', 'regex': '^\\d{9}$', 'aliases': [], 'desc': 'TIN (9 digits) [LOW confidence]'},
    },
    'MX': {
        'ORG': {'sap_code': 'MX1', 'regex': '^[A-Z]{2,3}\\d{6}[A-Z0-9]{3}$', 'aliases': ['^[A-Z0-9]{10,13}$'], 'desc': 'RFC Persona Moral (12 chars; 11 if Ñ/& stripped); alias: 10-13 alphanumeric'},
        'IND': {'sap_code': 'MX3', 'regex': '^[A-Z]{3,4}\\d{6}[A-Z0-9]{3}$', 'aliases': ['^[A-Z0-9]{10,13}$'], 'desc': 'RFC Persona Física (13 chars; 12 if Ñ/& stripped); alias: 10-13 alphanumeric'},
        'GENERIC': {'sap_code': 'MX1', 'regex': '^[A-Z]{2,4}\\d{6}[A-Z0-9]{3}$', 'aliases': ['^[A-Z0-9]{10,13}$'], 'desc': 'RFC (10-13 chars after stripping Ñ/&)'},
    },
    'MZ': {
        'ORG': {'sap_code': 'MZ1', 'regex': '^\\d{9}$', 'aliases': [], 'desc': 'NUIT (9 digits)'},
        'IND': {'sap_code': 'MZ1', 'regex': '^\\d{9}$', 'aliases': [], 'desc': 'NUIT (9 digits)'},
        'GENERIC': {'sap_code': 'MZ1', 'regex': '^\\d{9}$', 'aliases': [], 'desc': 'NUIT (9 digits)'},
    },
    'NG': {
        'ORG': {'sap_code': 'NG3', 'regex': '^\\d{12}$', 'aliases': ['^\\d{10}$', '^\\d{13}$'], 'desc': 'TIN (12 digits after stripping hyphen; 10 or 13 digit variants accepted)'},
        'IND': {'sap_code': 'NG3', 'regex': '^\\d{10}$', 'aliases': ['^\\d{12}$', '^\\d{13}$'], 'desc': 'TIN (10-13 digit variants)'},
        'GENERIC': {'sap_code': 'NG3', 'regex': '^\\d{10,13}$', 'aliases': [], 'desc': 'TIN (10-13 digits)'},
    },
    'NL': {
        'ORG': {'sap_code': 'NL1', 'regex': '^\\d{9}$', 'aliases': ['^\\d{8}$'], 'desc': 'RSIN (9 digits); KvK (8 digits) as alias'},
        'IND': {'sap_code': 'NL2', 'regex': '^\\d{9}$', 'aliases': [], 'desc': 'BSN (9 digits)'},
        'GENERIC': {'sap_code': 'NL3', 'regex': '^\\d{8,9}$', 'aliases': [], 'desc': 'RSIN, BSN or KvK'},
    },
    'NO': {
        'ORG': {'sap_code': 'NO2', 'regex': '^[89]\\d{8}$', 'aliases': ['^\\d{9}$'], 'desc': 'Organisasjonsnummer (9 digits, starts 8 or 9)'},
        'IND': {'sap_code': 'NO1', 'regex': '^\\d{11}$', 'aliases': [], 'desc': 'Fødselsnummer (11 digits)'},
        'GENERIC': {'sap_code': 'NO2', 'regex': '^\\d{9,11}$', 'aliases': [], 'desc': 'Org.nr. (9) or Fødselsnummer (11)'},
    },
    'NZ': {
        'ORG': {'sap_code': 'NZ3', 'regex': '^\\d{8,9}$', 'aliases': [], 'desc': 'IRD Number (8-9 digits)'},
        'IND': {'sap_code': 'NZ3', 'regex': '^\\d{8,9}$', 'aliases': [], 'desc': 'IRD Number (8-9 digits)'},
        'GENERIC': {'sap_code': 'NZ3', 'regex': '^\\d{8,9}$', 'aliases': [], 'desc': 'IRD Number (8-9 digits)'},
    },
    'PA': {
        'ORG': {'sap_code': 'PA3', 'regex': '^\\d{5,15}$', 'aliases': ['^.+$'], 'desc': 'RUC (variable, hyphens stripped)'},
        'IND': {'sap_code': 'PA3', 'regex': '^\\d{5,15}$', 'aliases': ['^.+$'], 'desc': 'Cédula (variable, hyphens stripped)'},
        'GENERIC': {'sap_code': 'PA3', 'regex': '^.+$', 'aliases': [], 'desc': 'Panama TIN (variable)'},
    },
    'PH': {
        'ORG': {'sap_code': 'PH1', 'regex': '^\\d{9}$', 'aliases': ['^\\d{12}$'], 'desc': 'TIN (9 digits; companies append 3-digit branch suffix → 12)'},
        'IND': {'sap_code': 'PH1', 'regex': '^\\d{9}$', 'aliases': [], 'desc': 'TIN (9 digits)'},
        'GENERIC': {'sap_code': 'PH1', 'regex': '^\\d{9,12}$', 'aliases': [], 'desc': 'TIN (9-12 digits)'},
    },
    'PL': {
        'ORG': {'sap_code': 'PL1', 'regex': '^\\d{10}$', 'aliases': [], 'desc': 'NIP (10 digits)'},
        'IND': {'sap_code': 'PL2', 'regex': '^\\d{10}$', 'aliases': ['^\\d{11}$'], 'desc': 'NIP (10 digits); PESEL (11 digits) as alias'},
        'GENERIC': {'sap_code': 'PL1', 'regex': '^\\d{10,11}$', 'aliases': [], 'desc': 'NIP or PESEL'},
    },
    'PS': {
        'ORG': {'sap_code': 'PS1', 'regex': '^\\d{9}$', 'aliases': ['^.+$'], 'desc': 'TIN (9 digits) [LOW confidence]'},
        'IND': {'sap_code': 'PS1', 'regex': '^\\d{9}$', 'aliases': ['^.+$'], 'desc': 'TIN (9 digits) [LOW confidence]'},
        'GENERIC': {'sap_code': 'PS1', 'regex': '^\\d{9}$', 'aliases': [], 'desc': 'TIN [LOW confidence]'},
    },
    'PT': {
        'ORG': {'sap_code': 'PT1', 'regex': '^5\\d{8}$', 'aliases': ['^\\d{9}$'], 'desc': 'NIPC (9 digits, starts with 5)'},
        'IND': {'sap_code': 'PT1', 'regex': '^[123]\\d{8}$', 'aliases': ['^\\d{9}$'], 'desc': 'NIF for individuals (9 digits, starts 1/2/3)'},
        'GENERIC': {'sap_code': 'PT1', 'regex': '^\\d{9}$', 'aliases': [], 'desc': 'NIF/NIPC (9 digits)'},
    },
    'PY': {
        'ORG': {'sap_code': 'PY3', 'regex': '^\\d{7,9}$', 'aliases': [], 'desc': 'RUC (6-8 digits + check digit, hyphen stripped)'},
        'IND': {'sap_code': 'PY3', 'regex': '^\\d{7,9}$', 'aliases': [], 'desc': 'RUC (same format for individuals)'},
        'GENERIC': {'sap_code': 'PY3', 'regex': '^\\d{7,9}$', 'aliases': [], 'desc': 'RUC (7-9 digits after stripping hyphen)'},
    },
    'QA': {
        'ORG': {'sap_code': 'QA1', 'regex': '^\\d{10}$', 'aliases': ['^.+$'], 'desc': 'TIN/CR (10 digits) [MED confidence]'},
        'IND': {'sap_code': 'QA1', 'regex': '^\\d{11}$', 'aliases': [], 'desc': 'Qatar ID (QID, 11 digits)'},
        'GENERIC': {'sap_code': 'QA1', 'regex': '^\\d{10,11}$', 'aliases': [], 'desc': 'TIN (10) or QID (11)'},
    },
    'RO': {
        'ORG': {'sap_code': 'RO1', 'regex': '^\\d{2,10}$', 'aliases': [], 'desc': 'CUI (2-10 digits)'},
        'IND': {'sap_code': 'RO2', 'regex': '^[1-9]\\d{12}$', 'aliases': [], 'desc': 'CNP (13 digits, first digit 1-9)'},
        'GENERIC': {'sap_code': 'RO1', 'regex': '^\\d{2,13}$', 'aliases': [], 'desc': 'CUI or CNP'},
    },
    'RS': {
        'ORG': {'sap_code': 'RS1', 'regex': '^\\d{9}$', 'aliases': [], 'desc': 'PIB (9 digits)'},
        'IND': {'sap_code': 'RS2', 'regex': '^\\d{13}$', 'aliases': [], 'desc': 'JMBG (13 digits)'},
        'GENERIC': {'sap_code': 'RS1', 'regex': '^\\d{9}$', 'aliases': ['^\\d{13}$'], 'desc': 'PIB (9) or JMBG (13)'},
    },
    'RU': {
        'ORG': {'sap_code': 'RU1', 'regex': '^\\d{10}$', 'aliases': [], 'desc': 'INN for organisations (10 digits)'},
        'IND': {'sap_code': 'RU2', 'regex': '^\\d{12}$', 'aliases': [], 'desc': 'INN for individuals (12 digits)'},
        'GENERIC': {'sap_code': 'RU1', 'regex': '^\\d{10}$', 'aliases': ['^\\d{12}$'], 'desc': 'INN (10 for org, 12 for individual)'},
    },
    'SA': {
        'ORG': {'sap_code': 'SA1', 'regex': '^3\\d{14}$', 'aliases': ['^\\d{15}$'], 'desc': 'ZATCA TIN (15 digits, starts with 3)'},
        'IND': {'sap_code': 'SA2', 'regex': '^[12]\\d{9}$', 'aliases': ['^\\d{10}$'], 'desc': 'National ID (10 digits, starts 1 for Saudis / 2 for Iqama)'},
        'GENERIC': {'sap_code': 'SA1', 'regex': '^\\d{10,15}$', 'aliases': [], 'desc': 'ZATCA TIN (15) or National ID (10)'},
    },
    'SB': {
        'ORG': {'sap_code': 'SB3', 'regex': '^\\d{9}$', 'aliases': ['^.+$'], 'desc': 'TIN (9 digits) [LOW confidence]'},
        'IND': {'sap_code': 'SB3', 'regex': '^\\d{9}$', 'aliases': ['^.+$'], 'desc': 'TIN (9 digits) [LOW confidence]'},
        'GENERIC': {'sap_code': 'SB3', 'regex': '^\\d{9}$', 'aliases': [], 'desc': 'TIN [LOW confidence]'},
    },
    'SC': {
        'ORG': {'sap_code': 'SC1', 'regex': '^\\d{7,9}$', 'aliases': ['^.+$'], 'desc': 'TIN (7-9 digits) [LOW confidence]'},
        'IND': {'sap_code': 'SC1', 'regex': '^\\d{7,9}$', 'aliases': ['^.+$'], 'desc': 'TIN (7-9 digits) [LOW confidence]'},
        'GENERIC': {'sap_code': 'SC1', 'regex': '^\\d{7,9}$', 'aliases': [], 'desc': 'TIN [LOW confidence]'},
    },
    'SE': {
        'ORG': {'sap_code': 'SE2', 'regex': '^\\d{10}$', 'aliases': [], 'desc': 'Organisationsnummer (10 digits, hyphen stripped)'},
        'IND': {'sap_code': 'SE1', 'regex': '^\\d{10}$', 'aliases': ['^\\d{12}$'], 'desc': 'Personnummer (10 or 12 digits, hyphen stripped)'},
        'GENERIC': {'sap_code': 'SE2', 'regex': '^\\d{10,12}$', 'aliases': [], 'desc': 'Org.nr. or Personnummer'},
    },
    'SI': {
        'ORG': {'sap_code': 'SI1', 'regex': '^\\d{8}$', 'aliases': [], 'desc': 'Davčna številka (8 digits)'},
        'IND': {'sap_code': 'SI1', 'regex': '^\\d{8}$', 'aliases': [], 'desc': 'Davčna številka (8 digits)'},
        'GENERIC': {'sap_code': 'SI1', 'regex': '^\\d{8}$', 'aliases': [], 'desc': 'Davčna številka (8 digits)'},
    },
    'SK': {
        'ORG': {'sap_code': 'SK1', 'regex': '^\\d{8}$', 'aliases': [], 'desc': 'IČO (8 digits)'},
        'IND': {'sap_code': 'SK2', 'regex': '^\\d{9,10}$', 'aliases': [], 'desc': 'Rodné číslo (9-10 digits, slash stripped)'},
        'GENERIC': {'sap_code': 'SK2', 'regex': '^\\d{8,10}$', 'aliases': [], 'desc': 'IČO or Rodné číslo'},
    },
    'SN': {
        'ORG': {'sap_code': 'SN3', 'regex': '^\\d{7}[A-Z]{1,2}$', 'aliases': [], 'desc': 'NINEA (7 digits + 1-2 letters)'},
        'IND': {'sap_code': 'SN3', 'regex': '^\\d{7}[A-Z]{1,2}$', 'aliases': ['^.+$'], 'desc': 'NINEA or NIN [MED confidence]'},
        'GENERIC': {'sap_code': 'SN3', 'regex': '^\\d{7}[A-Z]{1,2}$', 'aliases': [], 'desc': 'NINEA (7+1-2 chars)'},
    },
    'SS': {
        'ORG': {'sap_code': 'SS3', 'regex': '^.+$', 'aliases': [], 'desc': 'No documented format [NO DATA]'},
        'IND': {'sap_code': 'SS3', 'regex': '^.+$', 'aliases': [], 'desc': 'No documented format [NO DATA]'},
        'GENERIC': {'sap_code': 'SS3', 'regex': '^.+$', 'aliases': [], 'desc': 'No documented format [NO DATA]'},
    },
    'SZ': {
        'ORG': {'sap_code': 'SZ1', 'regex': '^\\d{9}$', 'aliases': ['^.+$'], 'desc': 'TIN (9 digits) [LOW confidence]'},
        'IND': {'sap_code': 'SZ1', 'regex': '^\\d{9}$', 'aliases': ['^.+$'], 'desc': 'TIN (9 digits) [LOW confidence]'},
        'GENERIC': {'sap_code': 'SZ1', 'regex': '^\\d{9}$', 'aliases': [], 'desc': 'TIN [LOW confidence]'},
    },
    'TH': {
        'ORG': {'sap_code': 'TH3', 'regex': '^\\d{13}$', 'aliases': [], 'desc': 'TIN / เลขประจำตัวผู้เสียภาษี (13 digits)'},
        'IND': {'sap_code': 'TH3', 'regex': '^\\d{13}$', 'aliases': [], 'desc': 'TIN based on National ID (13 digits)'},
        'GENERIC': {'sap_code': 'TH3', 'regex': '^\\d{13}$', 'aliases': [], 'desc': 'TIN (13 digits)'},
    },
    'TR': {
        'ORG': {'sap_code': 'TR1', 'regex': '^\\d{10}$', 'aliases': [], 'desc': 'Vergi Kimlik Numarası / VKN (10 digits)'},
        'IND': {'sap_code': 'TR2', 'regex': '^[1-9]\\d{9}[02468]$', 'aliases': ['^\\d{11}$'], 'desc': 'TC Kimlik No (11 digits, first ≥ 1, last even)'},
        'GENERIC': {'sap_code': 'TR2', 'regex': '^\\d{10,11}$', 'aliases': [], 'desc': 'VKN (10) or TC Kimlik (11)'},
    },
    'TW': {
        'ORG': {'sap_code': 'TW1', 'regex': '^\\d{8}$', 'aliases': [], 'desc': 'GUI Number / 統一編號 (8 digits)'},
        'IND': {'sap_code': 'TW2', 'regex': '^[A-Z]\\d{9}$', 'aliases': [], 'desc': 'National ID / 身分證字號 (1 letter + 9 digits)'},
        'GENERIC': {'sap_code': 'TW1', 'regex': '^\\d{8}$', 'aliases': ['^[A-Z]\\d{9}$'], 'desc': 'GUI (8 digits) or National ID (10 chars)'},
    },
    'TZ': {
        'ORG': {'sap_code': 'TZ3', 'regex': '^\\d{9}$', 'aliases': [], 'desc': 'TIN (9 digits)'},
        'IND': {'sap_code': 'TZ3', 'regex': '^\\d{9}$', 'aliases': [], 'desc': 'TIN (9 digits)'},
        'GENERIC': {'sap_code': 'TZ3', 'regex': '^\\d{9}$', 'aliases': [], 'desc': 'TIN (9 digits)'},
    },
    'UA': {
        'ORG': {'sap_code': 'UA2', 'regex': '^\\d{8}$', 'aliases': [], 'desc': 'EDRPOU (8 digits)'},
        'IND': {'sap_code': 'UA1', 'regex': '^\\d{10}$', 'aliases': [], 'desc': 'RNOKPP / INN (10 digits)'},
        'GENERIC': {'sap_code': 'UA1', 'regex': '^\\d{8,10}$', 'aliases': [], 'desc': 'EDRPOU (8) or RNOKPP (10)'},
    },
    'UG': {
        'ORG': {'sap_code': 'UG1', 'regex': '^\\d{10}$', 'aliases': [], 'desc': 'TIN (10 digits)'},
        'IND': {'sap_code': 'UG1', 'regex': '^\\d{10}$', 'aliases': [], 'desc': 'TIN (10 digits)'},
        'GENERIC': {'sap_code': 'UG1', 'regex': '^\\d{10}$', 'aliases': [], 'desc': 'TIN (10 digits)'},
    },
    'US': {
        'ORG': {'sap_code': 'US1', 'regex': '^\\d{9}$', 'aliases': [], 'desc': 'EIN (9 digits, hyphens stripped)'},
        'IND': {'sap_code': 'US2', 'regex': '^\\d{9}$', 'aliases': [], 'desc': 'SSN or ITIN (9 digits, hyphens stripped)'},
        'GENERIC': {'sap_code': 'US1', 'regex': '^\\d{9}$', 'aliases': [], 'desc': 'EIN/SSN/ITIN (9 digits)'},
    },
    'UY': {
        'ORG': {'sap_code': 'UY3', 'regex': '^\\d{12}$', 'aliases': [], 'desc': 'RUT (12 digits)'},
        'IND': {'sap_code': 'UY3', 'regex': '^\\d{12}$', 'aliases': [], 'desc': 'RUT (12 digits)'},
        'GENERIC': {'sap_code': 'UY3', 'regex': '^\\d{12}$', 'aliases': [], 'desc': 'RUT (12 digits)'},
    },
    'VE': {
        'ORG': {'sap_code': 'VE1', 'regex': '^[JGECV]\\d{9}$', 'aliases': [], 'desc': 'RIF for entities (prefix J/G/E/C/V + 9 digits, hyphen stripped)'},
        'IND': {'sap_code': 'VE2', 'regex': '^[VE]\\d{8,10}$', 'aliases': [], 'desc': 'RIF for individuals (V/E prefix + 8-10 digits, hyphen stripped)'},
        'GENERIC': {'sap_code': 'VE1', 'regex': '^[A-Z]\\d{8,10}$', 'aliases': [], 'desc': 'RIF (letter prefix + digits)'},
    },
    'VN': {
        'ORG': {'sap_code': 'VN1', 'regex': '^\\d{10}$', 'aliases': [], 'desc': 'MST / Mã số thuế (10 digits)'},
        'IND': {'sap_code': 'VN1', 'regex': '^\\d{10}$', 'aliases': ['^\\d{13}$'], 'desc': 'MST (10 digits; branch codes strip hyphen → 13)'},
        'GENERIC': {'sap_code': 'VN1', 'regex': '^\\d{10,13}$', 'aliases': [], 'desc': 'MST (10-13 digits)'},
    },
    'ZA': {
        'ORG': {'sap_code': 'ZA3', 'regex': '^\\d{10}$', 'aliases': [], 'desc': 'TIN / Income Tax Reference (10 digits)'},
        'IND': {'sap_code': 'ZA5', 'regex': '^\\d{10}$', 'aliases': [], 'desc': 'Tax Reference Number (10 digits)'},
        'GENERIC': {'sap_code': 'ZA3', 'regex': '^\\d{10}$', 'aliases': [], 'desc': 'TIN (10 digits)'},
    },
    'ZM': {
        'ORG': {'sap_code': 'ZM1', 'regex': '^\\d{10}$', 'aliases': [], 'desc': 'TPIN (10 digits)'},
        'IND': {'sap_code': 'ZM1', 'regex': '^\\d{10}$', 'aliases': [], 'desc': 'TPIN (10 digits)'},
        'GENERIC': {'sap_code': 'ZM1', 'regex': '^\\d{10}$', 'aliases': [], 'desc': 'TPIN (10 digits)'},
    },
}
