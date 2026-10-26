"""API v1 router aggregating all endpoints."""

from fastapi import APIRouter

from app.api.v1.examples import router as examples_router
from app.api.v1.health import router as health_router
from app.api.v1.query import router as query_router
from app.api.v1.schema import router as schema_router
from app.api.v1.sql import router as sql_router

api_v1_router = APIRouter(prefix="/api/v1")

api_v1_router.include_router(health_router)
api_v1_router.include_router(schema_router)
api_v1_router.include_router(examples_router)
api_v1_router.include_router(query_router)
api_v1_router.include_router(sql_router)
