from fastapi import APIRouter, HTTPException, status
from sqlalchemy.exc import IntegrityError

from app.dependencies import DbSession
from app.models import User
from app.schemas import UserCreate, UserRead

router = APIRouter(prefix="/api/v1/users", tags=["users"])


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, db: DbSession) -> User:
    user = User(email=str(payload.email), display_name=payload.display_name)
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with that email already exists",
        ) from exc
    db.refresh(user)
    return user
