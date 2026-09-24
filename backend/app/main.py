from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import address_cleansing, chat, geisterobjekte, health, load_data, projects, sap_carp, tenants
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
