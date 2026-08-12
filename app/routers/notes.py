from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Query, Response, status
from sqlalchemy import func, or_, select, update

from app.dependencies import (
    CurrentUser,
    DbSession,
    get_note_for_member,
    require_team_membership,
)
from app.models import MembershipRole, Note
from app.schemas import NoteCreate, NoteList, NoteRead, NoteUpdate

router = APIRouter(prefix="/api/v1", tags=["notes"])
_WRITE_ROLES = {MembershipRole.OWNER, MembershipRole.EDITOR}
_ETAG_PATTERN = re.compile(r'^"([1-9][0-9]*)"$')


def _etag(version: int) -> str:
    return f'"{version}"'


def _parse_if_match(if_match: str | None) -> int:
    if if_match is None:
        raise HTTPException(
            status_code=428,
            detail="If-Match header is required for note updates",
        )
    match = _ETAG_PATTERN.fullmatch(if_match.strip())
    if match is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='If-Match must contain a note ETag such as "1"',
        )
    return int(match.group(1))


@router.post(
    "/teams/{team_id}/notes",
    response_model=NoteRead,
    status_code=status.HTTP_201_CREATED,
)
def create_note(
    team_id: UUID,
    payload: NoteCreate,
    response: Response,
    db: DbSession,
    current_user: CurrentUser,
) -> Note:
    require_team_membership(
        db,
        team_id=team_id,
        user_id=current_user.id,
        allowed_roles=_WRITE_ROLES,
    )
    note = Note(
        team_id=team_id,
        author_id=current_user.id,
        last_edited_by_user_id=current_user.id,
        title=payload.title,
        body=payload.body,
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    response.headers["ETag"] = _etag(note.version)
    return note


@router.get("/teams/{team_id}/notes", response_model=NoteList)
def list_notes(
    team_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
    query: Annotated[str | None, Query(max_length=200)] = None,
    include_archived: bool = False,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> NoteList:
    require_team_membership(db, team_id=team_id, user_id=current_user.id)

    filters = [Note.team_id == team_id]
    if not include_archived:
        filters.append(Note.archived_at.is_(None))
    if query and (normalized_query := query.strip()):
        filters.append(
            or_(
                Note.title.contains(normalized_query, autoescape=True),
                Note.body.contains(normalized_query, autoescape=True),
            )
        )

    total = db.scalar(select(func.count()).select_from(Note).where(*filters)) or 0
    notes = db.scalars(
        select(Note)
        .where(*filters)
        .order_by(Note.updated_at.desc(), Note.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return NoteList(
        items=[NoteRead.model_validate(note) for note in notes],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/notes/{note_id}", response_model=NoteRead)
def get_note(
    note_id: UUID,
    response: Response,
    db: DbSession,
    current_user: CurrentUser,
) -> Note:
    note = get_note_for_member(db, note_id=note_id, user_id=current_user.id)
    response.headers["ETag"] = _etag(note.version)
    return note


@router.patch("/notes/{note_id}", response_model=NoteRead)
def update_note(
    note_id: UUID,
    payload: NoteUpdate,
    response: Response,
    db: DbSession,
    current_user: CurrentUser,
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> Note:
    expected_version = _parse_if_match(if_match)
    existing = get_note_for_member(db, note_id=note_id, user_id=current_user.id)
    require_team_membership(
        db,
        team_id=existing.team_id,
        user_id=current_user.id,
        allowed_roles=_WRITE_ROLES,
    )

    if existing.version != expected_version:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail="The note has changed; fetch the latest version and retry",
        )

    now = datetime.now(timezone.utc)
    values: dict[str, object] = {
        "last_edited_by_user_id": current_user.id,
        "updated_at": now,
        "version": Note.version + 1,
    }
    if "title" in payload.model_fields_set:
        values["title"] = payload.title
    if "body" in payload.model_fields_set:
        values["body"] = payload.body
    if "archived" in payload.model_fields_set:
        values["archived_at"] = now if payload.archived else None

    result = db.execute(
        update(Note)
        .where(Note.id == note_id, Note.version == expected_version)
        .values(**values)
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail="The note changed while this update was being processed",
        )

    db.commit()
    db.expire_all()
    updated_note = db.get(Note, note_id)
    if updated_note is None:  # Defensive: this endpoint does not delete notes.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
    response.headers["ETag"] = _etag(updated_note.version)
    return updated_note
