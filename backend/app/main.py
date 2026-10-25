"""FastAPI application entrypoint for DataQuery."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.middleware import RequestIDMiddleware
from app.api.v1.health import router as root_health_router
from app.api.v1.router import api_v1_router
from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.core.logging import get_logger, setup_logging
from app.db.engines import dispose_engines

logger = get_logger("app.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown lifecycles."""
    setup_logging()
    logger.info("Initializing DataQuery application services...")
    yield
    logger.info("Disposing database connection pools...")
    dispose_engines()
    logger.info("Shutdown complete.")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance."""
    settings = get_settings()

    app = FastAPI(
        title="DataQuery — AI-Powered Analytics Assistant",
        description=(
            "Translates natural language questions into safe, read-only SQL queries "
            "against an e-commerce PostgreSQL database, validates queries via sqlglot, "
            "executes with strict timeout limits, and provides plain-English explanations."
        ),
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # 1. Custom Request-ID and timing middleware
    app.add_middleware(RequestIDMiddleware)

    # 2. CORS middleware configured from environment settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "X-Process-Time"],
    )

    # 3. Global error envelope exception handlers
    register_error_handlers(app)

    # 4. Mount API v1 router
    app.include_router(api_v1_router)

    # 5. Direct root /health endpoint alongside /api/v1/health
    app.include_router(root_health_router)

    # 6. Test route to verify unhandled 500 exception masking
    @app.get("/debug/crash", include_in_schema=False)
    def debug_crash() -> None:
        """Trigger an unhandled exception to verify the 500 error envelope."""
        raise RuntimeError("Induced unhandled exception for testing 500 error envelope.")

    return app


app = create_app()
