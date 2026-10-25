"""Dependencies shared by every module: settings, the database and the model calls.

create_app() puts them on app.state once (the database when the lifespan starts); routes ask for
them through these Annotated types instead of reaching into app.state themselves.
"""

from typing import Annotated

from fastapi import Depends, Request

from app.core.config import Settings
from app.core.db import Database
from app.llm.models import Models


def get_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_db(request: Request) -> Database:
    db: Database = request.app.state.db
    return db


def get_models(request: Request) -> Models:
    models: Models = request.app.state.models
    return models


SettingsDep = Annotated[Settings, Depends(get_settings)]
DatabaseDep = Annotated[Database, Depends(get_db)]
ModelsDep = Annotated[Models, Depends(get_models)]
