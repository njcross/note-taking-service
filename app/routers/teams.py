from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.dependencies import CurrentUser, DbSession, require_team_membership
from app.models import MembershipRole, Team, TeamMembership, User
from app.schemas import MemberAdd, MemberRead, TeamCreate, TeamRead, TeamSummary

router = APIRouter(prefix="/api/v1/teams", tags=["teams"])


@router.post("", response_model=TeamRead, status_code=status.HTTP_201_CREATED)
def create_team(payload: TeamCreate, db: DbSession, current_user: CurrentUser) -> Team:
    team = Team(name=payload.name, created_by_user_id=current_user.id)
    db.add(team)
    db.flush()
    db.add(
        TeamMembership(
            team_id=team.id,
            user_id=current_user.id,
            role=MembershipRole.OWNER,
        )
    )
    db.commit()
    db.refresh(team)
    return team


@router.get("", response_model=list[TeamSummary])
def list_my_teams(db: DbSession, current_user: CurrentUser) -> list[TeamSummary]:
    rows = db.execute(
        select(Team, TeamMembership.role)
        .join(TeamMembership, TeamMembership.team_id == Team.id)
        .where(TeamMembership.user_id == current_user.id)
        .order_by(Team.name.asc(), Team.id.asc())
    ).all()
    return [
        TeamSummary(
            id=team.id,
            name=team.name,
            created_by_user_id=team.created_by_user_id,
            created_at=team.created_at,
            role=role,
        )
        for team, role in rows
    ]


@router.get("/{team_id}", response_model=TeamRead)
def get_team(team_id: UUID, db: DbSession, current_user: CurrentUser) -> Team:
    require_team_membership(db, team_id=team_id, user_id=current_user.id)
    team = db.get(Team, team_id)
    if team is None:  # Defensive: membership and team are protected by a foreign key.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
    return team


@router.post(
    "/{team_id}/members",
    response_model=MemberRead,
    status_code=status.HTTP_201_CREATED,
)
def add_member(
    team_id: UUID,
    payload: MemberAdd,
    db: DbSession,
    current_user: CurrentUser,
) -> MemberRead:
    require_team_membership(
        db,
        team_id=team_id,
        user_id=current_user.id,
        allowed_roles={MembershipRole.OWNER},
    )

    user = db.get(User, payload.user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    membership = TeamMembership(team_id=team_id, user_id=user.id, role=payload.role)
    db.add(membership)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User is already a member of this team",
        ) from exc
    db.refresh(membership)
    return MemberRead(
        user_id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=membership.role,
        joined_at=membership.joined_at,
    )


@router.get("/{team_id}/members", response_model=list[MemberRead])
def list_members(
    team_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> list[MemberRead]:
    require_team_membership(db, team_id=team_id, user_id=current_user.id)
    rows = db.execute(
        select(TeamMembership, User)
        .join(User, User.id == TeamMembership.user_id)
        .where(TeamMembership.team_id == team_id)
        .order_by(User.display_name.asc(), User.id.asc())
    ).all()
    return [
        MemberRead(
            user_id=user.id,
            email=user.email,
            display_name=user.display_name,
            role=membership.role,
            joined_at=membership.joined_at,
        )
        for membership, user in rows
    ]
