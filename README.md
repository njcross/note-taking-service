A runnable REST service for a note-taking product shared by several small teams. The service
supports users, team membership, role-based access, shared notes, search, pagination,
archive/restore, and conflict-safe editing.

The implementation is intentionally small enough to review in one sitting while still showing
where authentication, authorization, persistence, concurrency, and API behavior belong.

## Scope and assumptions

Included:

- Users and teams, connected through explicit memberships.
- `owner`, `editor`, and `viewer` roles.
- Team-scoped note creation, reading, editing, search, pagination, archive, and restore.
- ETag-based optimistic concurrency so one editor cannot silently overwrite another editor's work.
- SQLite persistence by default, with SQLAlchemy keeping the data layer portable.
- Automated tests, Docker support, and continuous integration.

Deliberately outside this time box: passwords or OAuth, attachments, rich-text rendering,
real-time collaboration, notifications, note revision history, and team/member administration
beyond adding a member.

## Technology choices

- Python 3.11+
- FastAPI and Pydantic
- SQLAlchemy 2.x
- SQLite for the runnable default
- pytest and FastAPI's test client

## Run locally

### macOS or Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
uvicorn app.main:app --reload
```

### Windows PowerShell

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
uvicorn app.main:app --reload
```

The API starts at `http://127.0.0.1:8000`. Interactive OpenAPI documentation is available at
`http://127.0.0.1:8000/docs`, and the health check is `GET /health`.

The first run creates `team_notes.db` in the project directory. Override the database with the
`DATABASE_URL` environment variable. Set `AUTO_CREATE_DB=false` when schema creation is managed
outside the application.

## Run with Docker

```bash
docker compose up --build
```

The Compose configuration exposes port `8000` and persists SQLite data in a named volume.

## Run tests and quality checks

```bash
python -m pytest
python -m pytest --cov=app --cov-report=term-missing
ruff check .
```

The submitted suite contains 18 tests and currently reports 96% application coverage. CI repeats
linting and tests on every push and pull request, with a 90% coverage floor.

## Identity boundary

Authenticated routes require an `X-User-ID` header containing an existing user UUID.

```http
X-User-ID: 2cc5f3e5-e94e-45ea-881e-0a46f9e14a21
```

This is **not production authentication**. It represents the identity assertion a trusted API
gateway or authentication middleware would normally provide. Authorization is still fully
implemented inside the service, which keeps the challenge focused on the note domain rather than
password storage or a particular identity vendor.

## API summary

| Method | Path | Access | Purpose |
|---|---|---|---|
| `GET` | `/health` | Public | Health check |
| `POST` | `/api/v1/users` | Public in this demo | Create a user |
| `POST` | `/api/v1/teams` | Authenticated | Create a team; caller becomes owner |
| `GET` | `/api/v1/teams` | Authenticated | List caller's teams and roles |
| `GET` | `/api/v1/teams/{team_id}` | Team member | Read a team |
| `POST` | `/api/v1/teams/{team_id}/members` | Owner | Add an editor or viewer |
| `GET` | `/api/v1/teams/{team_id}/members` | Team member | List the team roster |
| `POST` | `/api/v1/teams/{team_id}/notes` | Owner/editor | Create a shared note |
| `GET` | `/api/v1/teams/{team_id}/notes` | Team member | List, search, and paginate notes |
| `GET` | `/api/v1/notes/{note_id}` | Team member | Read one note and its ETag |
| `PATCH` | `/api/v1/notes/{note_id}` | Owner/editor | Edit, archive, or restore with `If-Match` |

Non-members receive `404` for team and note resources rather than a response that confirms the
resource exists.

### Role matrix

| Action | Owner | Editor | Viewer |
|---|:---:|:---:|:---:|
| Read team, roster, and notes | Yes | Yes | Yes |
| Create and edit notes | Yes | Yes | No |
| Archive and restore notes | Yes | Yes | No |
| Add team members | Yes | No | No |

## Example workflow

Create two users:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/users \
  -H "Content-Type: application/json" \
  -d '{"email":"alice@example.com","display_name":"Alice"}'

curl -X POST http://127.0.0.1:8000/api/v1/users \
  -H "Content-Type: application/json" \
  -d '{"email":"bob@example.com","display_name":"Bob"}'
```

Copy the returned IDs into `ALICE_ID` and `BOB_ID`, then create a team:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/teams \
  -H "X-User-ID: $ALICE_ID" \
  -H "Content-Type: application/json" \
  -d '{"name":"Product"}'
```

Copy the returned team ID into `TEAM_ID`, then add Bob as an editor:

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/teams/$TEAM_ID/members" \
  -H "X-User-ID: $ALICE_ID" \
  -H "Content-Type: application/json" \
  -d "{\"user_id\":\"$BOB_ID\",\"role\":\"editor\"}"
```

Create a note:

```bash
curl -i -X POST "http://127.0.0.1:8000/api/v1/teams/$TEAM_ID/notes" \
  -H "X-User-ID: $BOB_ID" \
  -H "Content-Type: application/json" \
  -d '{"title":"Launch plan","body":"Draft rollout notes"}'
```

The response includes `ETag: "1"`. Copy the note ID into `NOTE_ID`, then update it with the version
that was read:

```bash
curl -i -X PATCH "http://127.0.0.1:8000/api/v1/notes/$NOTE_ID" \
  -H "X-User-ID: $BOB_ID" \
  -H 'If-Match: "1"' \
  -H "Content-Type: application/json" \
  -d '{"body":"Reviewed rollout notes"}'
```

A successful update returns `ETag: "2"`. Reusing `If-Match: "1"` returns `412 Precondition Failed`
instead of overwriting the newer content.

Archive or restore through the same endpoint:

```json
{"archived": true}
```

```json
{"archived": false}
```

Archived notes are excluded from list results unless `include_archived=true` is supplied. List
queries also accept `query`, `page`, and `page_size` parameters.

## Data model

```text
User 1 --- * TeamMembership * --- 1 Team
                                      |
                                      *
                                     Note
```

A note belongs to exactly one team. Its original author and most recent editor are retained. Team
membership is the authorization boundary; notes do not carry a separate access-control list.

All identifiers are UUIDs. Timestamps are normalized to UTC. Foreign-key enforcement is explicitly
enabled for SQLite, and note-list indexes cover the common team/update and team/archive access
patterns.