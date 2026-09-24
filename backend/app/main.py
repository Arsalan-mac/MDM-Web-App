from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import (
    address_cleansing,
    chat,
    delete_records,
    geisterobjekte,
    health,
    load_data,
    projects,
    quality,
    register_cleansing,
    sap_carp,
    sap_template,
    tax_cleansing,
    tenants,
)
from app.config import get_settings

settings = get_settings()

app = FastAPI(title="MDM Web App API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(tenants.router)
app.include_router(projects.router)
app.include_router(load_data.router)
app.include_router(address_cleansing.router)
app.include_router(chat.router)
app.include_router(geisterobjekte.router)
app.include_router(sap_carp.router)
app.include_router(quality.router)
app.include_router(tax_cleansing.router)
app.include_router(sap_template.router)
app.include_router(register_cleansing.router)
app.include_router(delete_records.router)
