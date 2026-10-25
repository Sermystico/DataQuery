"""API middleware for request tracking and observability."""

import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import get_logger

logger = get_logger("app.api.middleware")


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware ensuring every request has a traceable request ID and timing header.

    - Reads existing 'X-Request-ID' from incoming headers or generates a new UUID.
    - Attaches 'request_id' to request.state.
    - Sets 'X-Request-ID' and 'X-Process-Time' on every response.
    - Emits structured access log line with latency and status.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        start_time = time.perf_counter()

        # Extract or generate request ID
        incoming_id = request.headers.get("X-Request-ID")
        request_id = incoming_id if incoming_id else f"req_{uuid.uuid4().hex[:12]}"
        request.state.request_id = request_id

        # Process request
        response = await call_next(request)

        # Calculate execution time
        process_time_ms = (time.perf_counter() - start_time) * 1000.0

        # Attach response headers
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = f"{process_time_ms:.2f}ms"

        # Log completion
        logger.info(
            "[%s] %s %s -> %d (%.2fms)",
            request_id,
            request.method,
            request.url.path,
            response.status_code,
            process_time_ms,
        )

        return response
