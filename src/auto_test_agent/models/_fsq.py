from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


FsqPlatform = Literal["android", "ios", "macos", "windows", "web"]


class FsqCaseConfig(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    schema_version: str = Field(alias="schemaVersion")
    name: str
    description: str = ""
    platform: FsqPlatform
    app_id: str | None = Field(default=None, alias="appId")
    url: str | None = None
    tags: list[str] = Field(default_factory=list)
    env: dict[str, str | int | float | bool] = Field(default_factory=dict)
    properties: dict[str, Any] = Field(default_factory=dict)


class FsqCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: Path
    config: FsqCaseConfig
    commands: list[Any]

    @property
    def id(self) -> str:
        return self.path.stem.replace(".codex", "")