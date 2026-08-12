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
