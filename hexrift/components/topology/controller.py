from __future__ import annotations

import random
import re
import shutil
from dataclasses import replace
from typing import TYPE_CHECKING

from hexrift.components.schema.models.fields import parse_host_port
from hexrift.components.topology.edit import (
    AddEdit,
    HysteriaSpec,
    NodeSpec,
    RealitySpec,
    RegionItem,
    RegionSpec,
    RemoveEdit,
    Topology,
)
from hexrift.constants import RegionType
from hexrift.core.controller import BaseController
from hexrift.errors import Error, TopologyError


if TYPE_CHECKING:
    from hexrift.app import HexRiftApp  # noqa: F401

VLESS_ROUTE_RANGE = (2000, 60000)
"""Inclusive range new exit regions draw their `vless_route` from."""


def region_prefix(node_id: str) -> str:
    """Leading lowercase letters of node id (`nlA20` → `nl`)."""

    prefix = re.split(r"[^a-z]", node_id, maxsplit=1)[0]
    if not prefix:
        raise TopologyError(f"Cannot derive region id from node id {node_id!r}, pass --region")
    return prefix


def pick_vless_route(used: set[int]) -> int:
    low, high = VLESS_ROUTE_RANGE
    free = [route for route in range(low, high + 1) if route not in used]
    if not free:
        raise TopologyError(f"No unused vless_route left in {low}..{high}, set one by hand")
    return random.choice(free)  # noqa: S311 — routing tag, not secret


def masquerade_url(dest: str) -> str:
    """`https://host` for reality dest, port kept unless 443."""

    host, port = parse_host_port(dest)
    if ":" in host:
        host = f"[{host}]"
    return f"https://{host}" if port == 443 else f"https://{host}:{port}"


class TopologyController(BaseController["HexRiftApp"]):
    def add_node(
        self,
        node_id: str,
        *,
        region_id: str | None = None,
        node_type: RegionType | None = None,
        hostname: str | None = None,
        ipv6: bool = True,
        reality: RealitySpec | None = None,
    ) -> AddEdit | None:
        """Add node to its region in topology file, creating region when needed. `None` when already present."""

        topo = Topology(self._read())
        if topo.has_node(node_id):
            return None
        region_id = region_id or region_prefix(node_id)
        existing = topo.region(region_id)
        if existing is not None:
            node_type = node_type or _region_type(existing)
            if existing.type != node_type:
                raise TopologyError(
                    f"Region {region_id!r} has type '{existing.type}', refusing to add a '{node_type}' node to it"
                )
        elif node_type is None:
            raise TopologyError(f"Region {region_id!r} does not exist, pass --type to create it")

        vless_route = None
        if existing is None and node_type == RegionType.EXIT:
            vless_route = pick_vless_route(topo.used_vless_routes)
        hostname = hostname or self._default_hostname(topo, node_id, node_type, region_id)
        hysteria = None
        if node_type == RegionType.EXIT:
            hysteria = HysteriaSpec(sni=hostname, masquerade_url=masquerade_url(reality.dest) if reality else None)
        node = NodeSpec(
            id=node_id,
            hostname=hostname,
            ipv6=ipv6,
            reality=reality,
            hysteria=hysteria,
        )
        edited = topo.add_node(RegionSpec(region_id, node_type, vless_route), node)
        self._write(edited.text)
        return replace(edited, validation_error=self._revalidate())

    def remove_node(self, node_id: str) -> RemoveEdit | None:
        """Drop node from topology file, keeping its region. `None` when not present."""

        topo = Topology(self._read())
        if not topo.has_node(node_id):
            return None
        edited = topo.remove_node(node_id)
        self._write(edited.text)
        return replace(edited, validation_error=self._revalidate())

    def _read(self) -> str:
        try:
            return self.app.yaml_path.read_bytes().decode()
        except OSError as e:
            raise TopologyError(f"Failed to read topology {self.app.yaml_path}: {e}") from e

    def _write(self, text: str) -> None:
        path = self.app.yaml_path.resolve()
        tmp = path.with_name(path.name + ".tmp")
        try:
            tmp.write_bytes(text.encode())
            shutil.copymode(path, tmp)
            tmp.replace(path)
        except OSError as e:
            tmp.unlink(missing_ok=True)
            raise TopologyError(f"Failed to write topology {self.app.yaml_path}: {e}") from e

    def _revalidate(self) -> str | None:
        try:
            self.app.schema.load(self.app.yaml_path)
        except Error as e:
            return str(e)
        return None

    @staticmethod
    def _default_hostname(topo: Topology, node_id: str, node_type: RegionType, region_id: str) -> str:
        """Exits live under `aphelion_domain`, hubs follow hub nodes already present, own region first."""

        if node_type == RegionType.EXIT:
            domain = topo.aphelion_domain or ""
        else:
            hubs = [(r, n) for r in topo.regions if r.type == RegionType.HUB for n in r.nodes if n.hostname]
            sibling = next((n for r, n in hubs if r.id == region_id), hubs[0][1] if hubs else None)
            domain = sibling.hostname.partition(".")[2] if sibling and sibling.hostname else ""
        if not domain:
            raise TopologyError(f"No {node_type} hostname domain to derive {node_id!r} from, pass --hostname")
        return f"{node_id}.{domain}"


def _region_type(region: RegionItem) -> RegionType:
    try:
        return RegionType(region.type)
    except ValueError as e:
        raise TopologyError(f"Region {region.id!r} has unknown type {region.type!r}") from e
