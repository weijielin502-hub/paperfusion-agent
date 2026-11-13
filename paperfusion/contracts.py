from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Task(StrictModel):
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]+$")
    title: str
    strategy: Literal["direct", "p2c"] = "direct"
    files: list[str] = Field(min_length=1)
    depends_on: list[str] = Field(default_factory=list)
    specification: str
    acceptance: list[str] = Field(min_length=1)
    paper_refs: list[str] = Field(default_factory=list)


class Plan(StrictModel):
    summary: str
    tasks: list[Task] = Field(min_length=1, max_length=12)

    @model_validator(mode="after")
    def ordered_dependencies(self):
        seen = set()
        for task in self.tasks:
            if task.id in seen or not set(task.depends_on).issubset(seen):
                raise ValueError("Task ids must be unique and dependencies must precede their consumers")
            for file in task.files:
                from pathlib import PurePosixPath
                path = PurePosixPath(file.replace("\\", "/"))
                if path.is_absolute() or ".." in path.parts or ":" in file:
                    raise ValueError("Task files must be relative workspace paths")
            seen.add(task.id)
        return self


class AgentResult(StrictModel):
    verdict: Literal["done", "approved", "changes_required", "blocked"]
    summary: str
    findings: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(min_length=1)


class RunSettings(StrictModel):
    goal: str
    project: str
    paper: str
    acceptance: str
    mode: Literal["live", "replay"] = "live"
    analysis: Literal["provided", "p2c"] = "provided"
    executor: Literal["docker", "local-trusted"] = "docker"
    max_attempts: int = Field(default=3, ge=1, le=10)
    max_tool_rounds: int = Field(default=16, ge=1, le=50)
    timeout_seconds: int = Field(default=60, ge=1, le=1800)
    model: str = ""
    auto_approve: bool = False
    force_fuse: bool = False
    baseline: bool = False

    @model_validator(mode="after")
    def live_sandbox(self):
        if self.mode == "live" and self.executor != "docker":
            raise ValueError("Live-generated code requires the Docker executor")
        return self
