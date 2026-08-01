"""Derived-identifier view models."""

from __future__ import annotations

from dataclasses import dataclass, field

from hexrift.constants import AccessType, RegionType


@dataclass(frozen=True)
class Guest:
    label: str
    uuid: str
    email: str
    short_id: str


@dataclass(frozen=True)
class Portal:
    id: str
    tag: str
    uuid: str
    email: str
    short_id: str
    users: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class User:
    username: str
    group: str
    access: list[AccessType]
    uuid: str
    email: str
    server_uuid: str | None = None
    server_email: str | None = None
    guests: list[Guest] = field(default_factory=list)


@dataclass(frozen=True)
class Group:
    id: str
    short_id: str


@dataclass(frozen=True)
class Node:
    id: str
    region: str
    type: RegionType
    short_id: str | None = None
    hub_exit_uuids: dict[str, str] | None = None
    hub_short_id: str | None = None
