from urllib.parse import urlsplit

from starlette.middleware.base import (
    BaseHTTPMiddleware,
)
from starlette.requests import Request
from starlette.responses import JSONResponse


SAFE_METHODS = {
    "GET",
    "HEAD",
    "OPTIONS",
    "TRACE",
}


def _normalize_origin(
    value: str,
) -> tuple[str, str, int] | None:
    try:
        parsed = urlsplit(value)

        if (
            parsed.scheme not in {"http", "https"}
            or parsed.hostname is None
        ):
            return None

        default_port = (
            443
            if parsed.scheme == "https"
            else 80
        )

        return (
            parsed.scheme.lower(),
            parsed.hostname.lower(),
            parsed.port or default_port,
        )

    except ValueError:
        return None


class CSRFMiddleware(BaseHTTPMiddleware):
    """
    Reject cross-origin browser mutations authenticated
    by the access-token cookie.

    Versioned API and remote-agent endpoints use their
    own bearer/API-key authentication and are excluded.
    """

    async def dispatch(
        self,
        request: Request,
        call_next,
    ):
        if request.method.upper() in SAFE_METHODS:
            return await call_next(request)

        if request.url.path.startswith("/api/"):
            return await call_next(request)

        if not request.cookies.get("access_token"):
            return await call_next(request)

        source_origin = (
            request.headers.get("origin")
            or request.headers.get("referer")
        )

        expected_origin = _normalize_origin(
            str(request.base_url)
        )

        supplied_origin = (
            _normalize_origin(source_origin)
            if source_origin
            else None
        )

        if (
            expected_origin is None
            or supplied_origin != expected_origin
        ):
            return JSONResponse(
                status_code=403,
                content={
                    "detail": (
                        "CSRF validation failed: "
                        "same-origin request required."
                    )
                },
            )

        return await call_next(request)