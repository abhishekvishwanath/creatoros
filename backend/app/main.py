from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Must be imported before any ORM operation runs: SQLAlchemy resolves string
# ForeignKey targets (e.g. content_items.opportunity_id -> "opportunities.id")
# lazily against whatever's registered on Base.metadata at mapper-configure
# time. Routes only import the domain modules they directly touch, so without
# this the app boots fine and 500s the first time a flush needs a table whose
# model nothing on that request's import path happened to pull in.
from app.infrastructure.db import all_models  # noqa: F401

from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging

configure_logging()
settings = get_settings()

app = FastAPI(title="Creator Intelligence OS API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.web_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
