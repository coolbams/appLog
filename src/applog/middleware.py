import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from .context import request_id_var

log = logging.getLogger("applog.requests")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Assigns a request id, logs one summary line per request,
    and logs full tracebacks for unhandled errors."""

    async def dispatch(self, request, call_next):
        rid = uuid.uuid4().hex[:8]
        request_id_var.set(rid)
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            log.exception("UNHANDLED ERROR %s %s", request.method, request.url.path)
            return JSONResponse(
                {"detail": "Internal server error", "request_id": rid},
                status_code=500,
                headers={"X-Request-ID": rid},
            )
        elapsed_ms = (time.perf_counter() - start) * 1000
        log.info(
            "%s %s -> %s (%.1f ms)",
            request.method, request.url.path, response.status_code, elapsed_ms,
        )
        response.headers["X-Request-ID"] = rid
        return response