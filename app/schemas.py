from __future__ import annotations

from datetime import datetime
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.models import MembershipRole


class ApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class UserCreate(BaseModel):
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=120)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).strip().lower()

    @field_validator("display_name")
    @classmethod
    def strip_display_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("display_name cannot be blank")
        return value


class UserRead(ApiModel):
    id: UUID
    email: EmailStr
    display_name: str
    created_at: datetime


class TeamCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name cannot be blank")
        return value


class TeamRead(ApiModel):
    id: UUID
    name: str
    created_by_user_id: UUID
    created_at: datetime


class TeamSummary(TeamRead):
    role: MembershipRole


class MemberAdd(BaseModel):
    user_id: UUID
    role: MembershipRole

    @field_validator("role")
    @classmethod
    def reject_owner_role(cls, value: MembershipRole) -> MembershipRole:
        if value is MembershipRole.OWNER:
            raise ValueError("new members can be added as editor or viewer")
        return value


class MemberRead(ApiModel):
    user_id: UUID
    email: EmailStr
    display_name: str
    role: MembershipRole
    joined_at: datetime


class NoteCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(default="", max_length=50_000)

    @field_validator("title")
    @classmethod
    def strip_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("title cannot be blank")
        return value


class NoteUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    body: str | None = Field(default=None, max_length=50_000)
    archived: bool | None = None

    @field_validator("title")
    @classmethod
    def strip_optional_title(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("title cannot be blank")
        return value

    @model_validator(mode="after")
    def validate_patch(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("at least one field must be supplied")

        for field_name in self.model_fields_set:
            if getattr(self, field_name) is None:
                raise ValueError(f"{field_name} cannot be null")
        return self


class NoteRead(ApiModel):
    id: UUID
    team_id: UUID
    author_id: UUID
    last_edited_by_user_id: UUID
    title: str
    body: str
    version: int
    archived: bool
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime


class NoteList(BaseModel):
    items: list[NoteRead]
    total: int
    page: int
    page_size: int
