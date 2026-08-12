from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient


def test_health_check(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_user_normalizes_input(client: TestClient) -> None:
    response = client.post(
        "/api/v1/users",
        json={"email": "  ALICE@Example.com ", "display_name": "  Alice Example  "},
    )

    assert response.status_code == 201
    assert response.json()["email"] == "alice@example.com"
    assert response.json()["display_name"] == "Alice Example"
    assert response.json()["created_at"].endswith("Z")


def test_duplicate_email_is_conflict(
    client: TestClient,
    create_user: Callable[..., dict[str, Any]],
) -> None:
    create_user(email="Alice@Example.com")

    response = client.post(
        "/api/v1/users",
        json={"email": "alice@example.com", "display_name": "Another Alice"},
    )

    assert response.status_code == 409


def test_authentication_header_is_required(client: TestClient) -> None:
    response = client.get("/api/v1/teams")

    assert response.status_code == 401
    assert response.json()["detail"] == "X-User-ID header is required"


def test_unknown_user_cannot_authenticate(client: TestClient) -> None:
    response = client.get(
        "/api/v1/teams",
        headers={"X-User-ID": "550e8400-e29b-41d4-a716-446655440000"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Unknown user"
