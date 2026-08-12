from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import TeamMembership, User, MembershipRole

DbSession = Annotated[Session, Depends(get_db)]
def get_current_user(
    db: DbSession,
    x_user_id: Annotated[UUID | None, Header(alias="X-User-ID")] = None,
) -> User:
    if x_user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-User-ID header is required",
        )

    user = db.get(User, x_user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unknown user",
        )
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_team_membership(
    db: Session,
    *,
    team_id: UUID,
    user_id: UUID,
    allowed_roles: set[MembershipRole] | None = None,
) -> TeamMembership:
    membership = db.scalar(
        select(TeamMembership).where(
            TeamMembership.team_id == team_id,
            TeamMembership.user_id == user_id,
        )
    )
    if membership is None:
        # A 404 avoids exposing team existence to non-members.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")

    if allowed_roles is not None and membership.role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your team role does not permit this action",
        )
    return membership