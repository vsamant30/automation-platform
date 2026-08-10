from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from app.core.csrf import CSRFMiddleware


async def successful_request(
    request: Request,
) -> JSONResponse:
    return JSONResponse(
        {
            "success": True,
        }
    )


csrf_test_app = Starlette(
    routes=[
        Route(
            "/browser-action",
            successful_request,
            methods=["GET", "POST"],
        ),
        Route(
            "/api/v1/agent-action",
            successful_request,
            methods=["POST"],
        ),
    ]
)

csrf_test_app.add_middleware(
    CSRFMiddleware,
)


def authenticated_client() -> TestClient:
    client = TestClient(csrf_test_app)

    client.cookies.set(
        "access_token",
        "test-cookie-token",
    )

    return client


def test_same_origin_request_is_allowed() -> None:
    client = authenticated_client()

    response = client.post(
        "/browser-action",
        headers={
            "Origin": "http://testserver",
        },
    )

    assert response.status_code == 200


def test_same_origin_referer_is_allowed() -> None:
    client = authenticated_client()

    response = client.post(
        "/browser-action",
        headers={
            "Referer": (
                "http://testserver/dashboard"
            ),
        },
    )

    assert response.status_code == 200


def test_cross_origin_request_is_rejected() -> None:
    client = authenticated_client()

    response = client.post(
        "/browser-action",
        headers={
            "Origin": "https://attacker.example",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"].startswith(
        "CSRF validation failed"
    )


def test_missing_origin_is_rejected() -> None:
    client = authenticated_client()

    response = client.post(
        "/browser-action",
    )

    assert response.status_code == 403


def test_api_request_is_not_subject_to_cookie_csrf() -> None:
    client = authenticated_client()

    response = client.post(
        "/api/v1/agent-action",
    )

    assert response.status_code == 200


def test_unauthenticated_login_style_request_is_allowed() -> None:
    client = TestClient(csrf_test_app)

    response = client.post(
        "/browser-action",
    )

    assert response.status_code == 200


def test_safe_request_is_allowed_without_origin() -> None:
    client = authenticated_client()

    response = client.get(
        "/browser-action",
    )

    assert response.status_code == 200