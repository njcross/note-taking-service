from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient


def test_editor_can_create_and_team_member_can_read_note(
    client: TestClient,
    create_user: Callable[..., dict[str, Any]],
    create_team: Callable[..., dict[str, Any]],
    add_member: Callable[..., dict[str, Any]],
    create_note: Callable[..., tuple[dict[str, Any], str]],
    auth_headers: Callable[[dict[str, Any]], dict[str, str]],
) -> None:
    owner = create_user()
    editor = create_user("editor@example.com", "Editor")
    viewer = create_user("viewer@example.com", "Viewer")
    team = create_team(owner)
    add_member(owner, team, editor, "editor")
    add_member(owner, team, viewer, "viewer")

    note, etag = create_note(editor, team)
    response = client.get(
        f"/api/v1/notes/{note['id']}",
        headers=auth_headers(viewer),
    )

    assert etag == '"1"'
    assert response.status_code == 200
    assert response.headers["etag"] == '"1"'
    assert response.json()["title"] == "Launch plan"


def test_viewer_cannot_create_or_update_notes(
    client: TestClient,
    create_user: Callable[..., dict[str, Any]],
    create_team: Callable[..., dict[str, Any]],
    add_member: Callable[..., dict[str, Any]],
    create_note: Callable[..., tuple[dict[str, Any], str]],
    auth_headers: Callable[[dict[str, Any]], dict[str, str]],
) -> None:
    owner = create_user()
    viewer = create_user("viewer@example.com", "Viewer")
    team = create_team(owner)
    add_member(owner, team, viewer, "viewer")
    note, _ = create_note(owner, team)

    create_response = client.post(
        f"/api/v1/teams/{team['id']}/notes",
        headers=auth_headers(viewer),
        json={"title": "Unauthorized"},
    )
    update_response = client.patch(
        f"/api/v1/notes/{note['id']}",
        headers={**auth_headers(viewer), "If-Match": '"1"'},
        json={"title": "Unauthorized"},
    )

    assert create_response.status_code == 403
    assert update_response.status_code == 403


def test_outsider_cannot_discover_note(
    client: TestClient,
    create_user: Callable[..., dict[str, Any]],
    create_team: Callable[..., dict[str, Any]],
    create_note: Callable[..., tuple[dict[str, Any], str]],
    auth_headers: Callable[[dict[str, Any]], dict[str, str]],
) -> None:
    owner = create_user()
    outsider = create_user("outsider@example.com", "Outsider")
    team = create_team(owner)
    note, _ = create_note(owner, team)

    response = client.get(
        f"/api/v1/notes/{note['id']}",
        headers=auth_headers(outsider),
    )

    assert response.status_code == 404


def test_update_uses_etag_and_rejects_stale_write(
    client: TestClient,
    create_user: Callable[..., dict[str, Any]],
    create_team: Callable[..., dict[str, Any]],
    create_note: Callable[..., tuple[dict[str, Any], str]],
    auth_headers: Callable[[dict[str, Any]], dict[str, str]],
) -> None:
    owner = create_user()
    team = create_team(owner)
    note, etag = create_note(owner, team)

    first_update = client.patch(
        f"/api/v1/notes/{note['id']}",
        headers={**auth_headers(owner), "If-Match": etag},
        json={"body": "Updated body"},
    )
    stale_update = client.patch(
        f"/api/v1/notes/{note['id']}",
        headers={**auth_headers(owner), "If-Match": etag},
        json={"body": "Stale body"},
    )

    assert first_update.status_code == 200
    assert first_update.headers["etag"] == '"2"'
    assert first_update.json()["version"] == 2
    assert stale_update.status_code == 412

    latest = client.get(
        f"/api/v1/notes/{note['id']}",
        headers=auth_headers(owner),
    )
    assert latest.json()["body"] == "Updated body"


def test_update_requires_valid_if_match_header(
    client: TestClient,
    create_user: Callable[..., dict[str, Any]],
    create_team: Callable[..., dict[str, Any]],
    create_note: Callable[..., tuple[dict[str, Any], str]],
    auth_headers: Callable[[dict[str, Any]], dict[str, str]],
) -> None:
    owner = create_user()
    team = create_team(owner)
    note, _ = create_note(owner, team)

    missing = client.patch(
        f"/api/v1/notes/{note['id']}",
        headers=auth_headers(owner),
        json={"body": "Updated"},
    )
    malformed = client.patch(
        f"/api/v1/notes/{note['id']}",
        headers={**auth_headers(owner), "If-Match": "1"},
        json={"body": "Updated"},
    )

    assert missing.status_code == 428
    assert malformed.status_code == 400


def test_archive_filter_search_and_pagination(
    client: TestClient,
    create_user: Callable[..., dict[str, Any]],
    create_team: Callable[..., dict[str, Any]],
    create_note: Callable[..., tuple[dict[str, Any], str]],
    auth_headers: Callable[[dict[str, Any]], dict[str, str]],
) -> None:
    owner = create_user()
    team = create_team(owner)
    first, first_etag = create_note(owner, team, "Roadmap", "Q4 launch milestones")
    create_note(owner, team, "Meeting", "Weekly planning notes")
    create_note(owner, team, "Ideas", "Future launch experiments")

    archived = client.patch(
        f"/api/v1/notes/{first['id']}",
        headers={**auth_headers(owner), "If-Match": first_etag},
        json={"archived": True},
    )
    default_list = client.get(
        f"/api/v1/teams/{team['id']}/notes",
        headers=auth_headers(owner),
    )
    search = client.get(
        f"/api/v1/teams/{team['id']}/notes",
        headers=auth_headers(owner),
        params={"query": "LAUNCH", "include_archived": True},
    )
    page = client.get(
        f"/api/v1/teams/{team['id']}/notes",
        headers=auth_headers(owner),
        params={"include_archived": True, "page": 2, "page_size": 2},
    )

    assert archived.status_code == 200
    assert archived.json()["archived"] is True
    assert archived.json()["updated_at"].endswith("Z")

    restored = client.patch(
        f"/api/v1/notes/{first['id']}",
        headers={**auth_headers(owner), "If-Match": archived.headers["etag"]},
        json={"archived": False},
    )

    assert restored.status_code == 200
    assert restored.json()["archived"] is False
    assert default_list.json()["total"] == 2
    assert search.json()["total"] == 2
    assert page.json()["total"] == 3
    assert len(page.json()["items"]) == 1


def test_empty_patch_is_rejected(
    client: TestClient,
    create_user: Callable[..., dict[str, Any]],
    create_team: Callable[..., dict[str, Any]],
    create_note: Callable[..., tuple[dict[str, Any], str]],
    auth_headers: Callable[[dict[str, Any]], dict[str, str]],
) -> None:
    owner = create_user()
    team = create_team(owner)
    note, etag = create_note(owner, team)

    response = client.patch(
        f"/api/v1/notes/{note['id']}",
        headers={**auth_headers(owner), "If-Match": etag},
        json={},
    )

    assert response.status_code == 422
