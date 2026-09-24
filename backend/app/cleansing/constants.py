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
    "RegisterCourtDate",
]
