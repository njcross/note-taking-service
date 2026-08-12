from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient


def test_team_creator_becomes_owner_and_can_list_team(
    client: TestClient,
    create_user: Callable[..., dict[str, Any]],
    create_team: Callable[..., dict[str, Any]],
    auth_headers: Callable[[dict[str, Any]], dict[str, str]],
) -> None:
    owner = create_user()
    team = create_team(owner)

    response = client.get("/api/v1/teams", headers=auth_headers(owner))

    assert response.status_code == 200
    assert response.json() == [{**team, "role": "owner"}]


def test_owner_can_add_member_and_members_can_list_roster(
    client: TestClient,
    create_user: Callable[..., dict[str, Any]],
    create_team: Callable[..., dict[str, Any]],
    add_member: Callable[..., dict[str, Any]],
    auth_headers: Callable[[dict[str, Any]], dict[str, str]],
) -> None:
    owner = create_user()
    editor = create_user("editor@example.com", "Ed Editor")
    team = create_team(owner)
    added = add_member(owner, team, editor, "editor")

    response = client.get(
        f"/api/v1/teams/{team['id']}/members",
        headers=auth_headers(editor),
    )

    assert response.status_code == 200
    assert added in response.json()
    assert {member["role"] for member in response.json()} == {"owner", "editor"}


def test_non_owner_cannot_add_members(
    client: TestClient,
    create_user: Callable[..., dict[str, Any]],
    create_team: Callable[..., dict[str, Any]],
    add_member: Callable[..., dict[str, Any]],
    auth_headers: Callable[[dict[str, Any]], dict[str, str]],
) -> None:
    owner = create_user()
    editor = create_user("editor@example.com", "Editor")
    candidate = create_user("candidate@example.com", "Candidate")
    team = create_team(owner)
    add_member(owner, team, editor, "editor")

    response = client.post(
        f"/api/v1/teams/{team['id']}/members",
        headers=auth_headers(editor),
        json={"user_id": candidate["id"], "role": "viewer"},
    )

    assert response.status_code == 403


def test_outsider_gets_not_found_for_team(
    client: TestClient,
    create_user: Callable[..., dict[str, Any]],
    create_team: Callable[..., dict[str, Any]],
    auth_headers: Callable[[dict[str, Any]], dict[str, str]],
) -> None:
    owner = create_user()
    outsider = create_user("outsider@example.com", "Outsider")
    team = create_team(owner)

    response = client.get(
        f"/api/v1/teams/{team['id']}",
        headers=auth_headers(outsider),
    )

    assert response.status_code == 404


def test_duplicate_membership_is_conflict(
    client: TestClient,
    create_user: Callable[..., dict[str, Any]],
    create_team: Callable[..., dict[str, Any]],
    add_member: Callable[..., dict[str, Any]],
    auth_headers: Callable[[dict[str, Any]], dict[str, str]],
) -> None:
    owner = create_user()
    editor = create_user("editor@example.com", "Editor")
    team = create_team(owner)
    add_member(owner, team, editor, "editor")

    response = client.post(
        f"/api/v1/teams/{team['id']}/members",
        headers=auth_headers(owner),
        json={"user_id": editor["id"], "role": "viewer"},
    )

    assert response.status_code == 409


def test_new_owner_role_is_rejected(
    client: TestClient,
    create_user: Callable[..., dict[str, Any]],
    create_team: Callable[..., dict[str, Any]],
    auth_headers: Callable[[dict[str, Any]], dict[str, str]],
) -> None:
    owner = create_user()
    candidate = create_user("candidate@example.com", "Candidate")
    team = create_team(owner)

    response = client.post(
        f"/api/v1/teams/{team['id']}/members",
        headers=auth_headers(owner),
        json={"user_id": candidate["id"], "role": "owner"},
    )

    assert response.status_code == 422