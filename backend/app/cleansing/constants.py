"""Constants mirrored from the original app's mdm_shared.py / data_upload_module.py.

Kept as a separate module (rather than only living on the Mandant model) so
later-ported stages (address/tax/register cleansing) can import the same
field-name constants the original app used, instead of re-typing string
literals.
"""

LOAD_DATE_COL = "Load_Date"
SOURCE_FILE_COL = "Source_FILE"
CHANGE_REASON_COL = "Change_Reason"

MANDANT_PRIMARY_KEY = "IDParty"
MANDANT_VAT_COL = "VATNumber"

# Columns that should have any trailing ".0" (from float-ified integers in
# spreadsheet tools) stripped during harmonization.
MANDANT_INTEGER_COLS = [
    "IDParty", "IsOrganisation", "IsIndividual", "IsProtected",
    "IsInactive", "IsVIP", "IsInBlackList",
]

# The standardized columns that get their own column on the Mandant model
# (app/models/tenant.py) - anything else present in an uploaded file lands
# in Mandant.extra instead.
STANDARD_MANDANT_COLUMNS = [
    "IDParty", "CompanyName", "CountryCode", "Address", "City", "ZipCode",
    "DistrictCode", "VATNumber", "IsOrganisation", "IsIndividual", "IsInactive",
    "UserCode_Added", "UserCode_Kummerer", "FiscalCode", "Email",
    "WebSite", "PhoneNumber", "FaxNumber", "DateFounded", "LiquidationDate",
    "RegisterCourtDate", "RegisterNumber", "RegisterCity", "RegisterCourtKindCode",
    "ViesNumber",
]

# Standard columns for the generic reference tables Geisterobjekte's ghost
# query needs (app/models/tenant.py - Auftrag, ConnectedParty, MandantGegner).
# Fixed source-system field names, not alias-mapped like Mandant's.
AUFTRAG_COLUMNS = [
    "IDProject", "IDParty", "ProjectNumber", "Year", "AssessmentYear",
    "ProjectName", "AddedDate", "ServiceName",
]
CONNECTED_PARTY_COLUMNS = ["IDParty", "IDParty_Related"]
MANDANT_GEGNER_COLUMNS = ["Client - IDParty", "Opponent - IDParty"]

# SAP-CARP-Ueberschreibung's Field-Mapping upload (app/cleansing/sap_carp_service.py).
FIELD_MAPPING_COLUMNS = ["Mandanten", "SAP-Allgemeine Stammdaten", "Condition"]
