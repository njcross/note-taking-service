from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture
def client() -> Iterator[TestClient]:
    app = create_app(
        Settings(
            app_name="Team Notes API Test",
            database_url="sqlite+pysqlite://",
            auto_create_db=True,
        )
    )
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def create_user(client: TestClient) -> Callable[..., dict[str, Any]]:
    def _create_user(
        email: str = "alice@example.com",
        display_name: str = "Alice",
    ) -> dict[str, Any]:
        response = client.post(
            "/api/v1/users",
            json={"email": email, "display_name": display_name},
        )
        assert response.status_code == 201, response.text
        return response.json()

    return _create_user


@pytest.fixture
def auth_headers() -> Callable[[dict[str, Any]], dict[str, str]]:
    def _auth_headers(user: dict[str, Any]) -> dict[str, str]:
        return {"X-User-ID": user["id"]}

    return _auth_headers


@pytest.fixture
def create_team(
    client: TestClient,
    auth_headers: Callable[[dict[str, Any]], dict[str, str]],
) -> Callable[..., dict[str, Any]]:
    def _create_team(owner: dict[str, Any], name: str = "Product") -> dict[str, Any]:
        response = client.post(
            "/api/v1/teams",
            headers=auth_headers(owner),
            json={"name": name},
        )
        assert response.status_code == 201, response.text
        return response.json()

    return _create_team


@pytest.fixture
def add_member(
    client: TestClient,
    auth_headers: Callable[[dict[str, Any]], dict[str, str]],
) -> Callable[..., dict[str, Any]]:
    def _add_member(
        owner: dict[str, Any],
        team: dict[str, Any],
        user: dict[str, Any],
        role: str = "editor",
    ) -> dict[str, Any]:
        response = client.post(
            f"/api/v1/teams/{team['id']}/members",
            headers=auth_headers(owner),
            json={"user_id": user["id"], "role": role},
        )
        assert response.status_code == 201, response.text
        return response.json()

    return _add_member


@pytest.fixture
def create_note(
    client: TestClient,
    auth_headers: Callable[[dict[str, Any]], dict[str, str]],
) -> Callable[..., tuple[dict[str, Any], str]]:
    def _create_note(
        user: dict[str, Any],
        team: dict[str, Any],
        title: str = "Launch plan",
        body: str = "Draft the rollout notes.",
    ) -> tuple[dict[str, Any], str]:
        response = client.post(
            f"/api/v1/teams/{team['id']}/notes",
            headers=auth_headers(user),
            json={"title": title, "body": body},
        )
        assert response.status_code == 201, response.text
        return response.json(), response.headers["etag"]

    return _create_note
