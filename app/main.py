from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import Settings
from app.db import init_db, make_engine, make_session_factory
from app.routers import health, users, teams, notes


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or Settings.from_env()
    engine = make_engine(resolved_settings.database_url)
    session_factory = make_session_factory(engine)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        if resolved_settings.auto_create_db:
            init_db(engine)
        yield
        engine.dispose()

    app = FastAPI(
        title=resolved_settings.app_name,
        version="0.1.0",
        description="A team-scoped REST API for creating and sharing notes.",
        lifespan=lifespan,
    )
    app.state.settings = resolved_settings
    app.state.engine = engine
    app.state.session_factory = session_factory

    app.include_router(health.router)
    app.include_router(users.router)
    app.include_router(teams.router)
    app.include_router(notes.router)
    return app


app = create_app()
