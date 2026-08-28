from __future__ import annotations

import re
from dataclasses import dataclass

import yaml

from hexrift.components.schema.models.fields import parse_host_port
from hexrift.constants import DNS_NAME_PATTERN, IDENTIFIER_PATTERN, RegionType
from hexrift.errors import TopologyError


REGION_INDENT = "  "
NODE_INDENT = "      "
NULL_TAG = "tag:yaml.org,2002:null"
SEQ_TAG = "tag:yaml.org,2002:seq"

_IDENTIFIER_RE = re.compile(IDENTIFIER_PATTERN)
_DNS_NAME_RE = re.compile(DNS_NAME_PATTERN)
_XRAY_PATH_RE = re.compile(r'/[^\s"\\]*')


def _natural_key(value: str) -> list[int | str]:
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", value)]


def _valid(what: str, value: str, pattern: re.Pattern[str]) -> None:
    if not pattern.fullmatch(value):
        raise TopologyError(f"Invalid {what}: {value!r}")


def _scalar_text(value: str) -> str:
    """Quote values YAML would not read back as identical plain strings (`no`, `123`, `/a:`)."""

    try:
        if yaml.safe_load(value) == value:
            return value
    except yaml.YAMLError:
        pass
    return f'"{value}"'


@dataclass(frozen=True)
class RealitySpec:
    dest: str
    xhttp_path: str
    server_names: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        try:
            parse_host_port(self.dest)
        except ValueError as e:
            raise TopologyError(f"Invalid reality dest: {e}") from e
        _valid("reality xhttp_path", self.xhttp_path, _XRAY_PATH_RE)
        for name in self.server_names:
            _valid("reality server name", name, _DNS_NAME_RE)


@dataclass(frozen=True)
class HysteriaSpec:
    sni: str
    masquerade_url: str | None = None


@dataclass(frozen=True)
class NodeSpec:
    id: str
    hostname: str
    ipv6: bool = True
    reality: RealitySpec | None = None
    hysteria: HysteriaSpec | None = None

    def __post_init__(self) -> None:
        _valid("node id", self.id, _IDENTIFIER_RE)
        _valid("hostname", self.hostname, _DNS_NAME_RE)


@dataclass(frozen=True)
class RegionSpec:
    id: str
    type: RegionType
    vless_route: int | None = None

    def __post_init__(self) -> None:
        _valid("region id", self.id, _IDENTIFIER_RE)


@dataclass(frozen=True)
class NodeItem:
    id: str | None
    hostname: str | None
    backup: bool
    start: int
    end: int


@dataclass(frozen=True)
class RegionItem:
    id: str | None
    type: str | None
    vless_routes: frozenset[int]
    nodes: tuple[NodeItem, ...]
    nodes_line: int | None
    nodes_error: str | None
    empty_flow_nodes: tuple[int, int, int] | None
    lb_fallback: str | None
    lb_fallback_line: int | None
    lb_strategy_end: int | None
    start: int
    end: int


@dataclass(frozen=True)
class RouteItem:
    destination: str | None
    start: int
    end: int


@dataclass(frozen=True)
class AddEdit:
    text: str
    region: RegionSpec
    node: NodeSpec
    created: bool
    set_lb_fallback: str | None = None
    validation_error: str | None = None


@dataclass(frozen=True)
class RemoveEdit:
    text: str
    region_id: str | None
    emptied: bool
    dropped_routes: tuple[str, ...] = ()
    dropped_lb_fallback: bool = False
    validation_error: str | None = None


def node_lines(node: NodeSpec) -> list[str]:
    lines = [f"{NODE_INDENT}- id: {_scalar_text(node.id)}", f"{NODE_INDENT}  hostname: {_scalar_text(node.hostname)}"]
    if not node.ipv6:
        lines.append(f"{NODE_INDENT}  ipv6: false")
    if node.reality is not None:
        names = ", ".join(_scalar_text(n) for n in node.reality.server_names)
        lines.append(f"{NODE_INDENT}  reality:")
        lines.append(f"{NODE_INDENT}    dest: {_scalar_text(node.reality.dest)}")
        if names:
            lines.append(f"{NODE_INDENT}    server_names: [{names}]")
        lines.append(f"{NODE_INDENT}    xhttp_path: {_scalar_text(node.reality.xhttp_path)}")
    if node.hysteria is not None:
        lines.append(f"{NODE_INDENT}  hysteria:")
        lines.append(f"{NODE_INDENT}    obfs: true")
        lines.append(f"{NODE_INDENT}    sni: {_scalar_text(node.hysteria.sni)}")
        if node.hysteria.masquerade_url is not None:
            lines.append(f"{NODE_INDENT}    masquerade_url: {_scalar_text(node.hysteria.masquerade_url)}")
    return lines


def region_lines(region: RegionSpec, node: NodeSpec) -> list[str]:
    lines = [f"{REGION_INDENT}- id: {_scalar_text(region.id)}", f"{REGION_INDENT}  type: {region.type}"]
    if region.vless_route is not None:
        lines.append(f"{REGION_INDENT}  vless_route: {region.vless_route}")
    lines.append(f"{REGION_INDENT}  nodes:")
    lines.extend(node_lines(node))
    return lines


class Topology:
    """One parsed topology file: immutable line buffer plus mark-located `regions:` entries."""

    def __init__(self, text: str) -> None:
        text = text if text.endswith("\n") else text + "\n"  # PyYAML end-marks stop one line short without it
        self._eol = "\r\n" if "\r\n" in text else "\n"
        self._lines = text.splitlines()
        root = _compose(text)
        self._regions_line, regions_value = _regions_entry(root)
        items = _block_items(regions_value)
        if items is None:
            raise TopologyError("'regions:' must be a bare key or a block sequence to edit")
        self.regions = tuple(_region_item(item, s, e) for item, s, e in _spans(items, regions_value.end_mark.line))
        self.aphelion_domain = _scalar(_entry(root, "global"), "aphelion_domain")
        self._hub_routes_line, self._hub_routes = _hub_route_items(root)

    def region(self, region_id: str) -> RegionItem | None:
        return next((r for r in self.regions if r.id == region_id), None)

    def has_node(self, node_id: str) -> bool:
        return any(n.id == node_id for r in self.regions for n in r.nodes)

    @property
    def used_vless_routes(self) -> set[int]:
        return {route for r in self.regions for route in r.vless_routes}

    def add_node(self, region: RegionSpec, node: NodeSpec) -> AddEdit:
        """Add `node` to `region`, creating missing region at end of section."""

        if self.has_node(node.id):
            raise TopologyError(f"Node {node.id!r} is already in the topology")
        lines = list(self._lines)
        existing = self.region(region.id)
        if existing is None:
            block = region_lines(region, node)
            if self.regions:
                at = _append_at(lines, self.regions[-1], REGION_INDENT)
                block = ["", *block]
            else:
                at = self._regions_line + 1
            lines[at:at] = block
            return AddEdit(self._render(lines), region, node, created=True)

        if existing.type != region.type:
            raise TopologyError(
                f"Region {region.id!r} has type '{existing.type}', refusing to add a '{region.type}' node to it"
            )
        if existing.nodes_error is not None:
            raise TopologyError(existing.nodes_error)
        if existing.nodes_line is None:
            raise TopologyError(f"Region {region.id!r} has no 'nodes:' key to add under")
        if existing.empty_flow_nodes is not None:
            row, first, last = existing.empty_flow_nodes
            lines[row] = (lines[row][:first] + lines[row][last:]).rstrip()
        at = _insert_at(lines, existing.nodes, existing.nodes_line, node.id)
        inserts = [(at, node_lines(node))]
        fallback = _fallback_to_set(existing)
        if fallback is not None:
            name, line = fallback
            inserts.append((line, [f"{REGION_INDENT}  lb_fallback: {_scalar_text(name)}"]))
        for pos, block in sorted(inserts, key=lambda i: i[0], reverse=True):
            lines[pos:pos] = block
        return AddEdit(self._render(lines), region, node, False, fallback[0] if fallback else None)

    def remove_node(self, node_id: str) -> RemoveEdit:
        """Drop `node_id`, plus hub routes and lb_fallback pointing at it, and hub routes to its region once emptied."""

        for region in self.regions:
            node = next((n for n in region.nodes if n.id == node_id), None)
            if node is not None:
                return self._remove(region, node)
        raise TopologyError(f"Node {node_id!r} is not in the topology")

    def _remove(self, region: RegionItem, node: NodeItem) -> RemoveEdit:
        if region.nodes_error is not None:
            raise TopologyError(region.nodes_error)
        lines = list(self._lines)
        emptied = len(region.nodes) == 1
        # routes to emptied region go, routes to id another region still owns stay
        gone = {region.id} if emptied else set()
        if node.id not in {r.id for r in self.regions} - gone:
            gone.add(node.id)
        dead = [r for r in self._hub_routes if r.destination is not None and r.destination in gone]
        routes = tuple(dict.fromkeys(r.destination for r in dead if r.destination is not None))
        for item in (node, *dead):
            _check_dash(lines, item)
        spans = [(i.start, _content_end(lines, i.start, i.end)) for i in (node, *dead)]
        if dead and len(dead) == len(self._hub_routes) and self._hub_routes_line is not None:
            spans.append((self._hub_routes_line, self._hub_routes_line + 1))
        fallback_line = region.lb_fallback_line if region.lb_fallback == node.id else None
        if fallback_line is not None:
            spans.append((fallback_line, fallback_line + 1))
        for start, end in sorted(spans, reverse=True):
            del lines[start:end]
        return RemoveEdit(self._render(lines), region.id, emptied, routes, fallback_line is not None)

    def _render(self, lines: list[str]) -> str:
        return self._eol.join(lines) + self._eol


class _Loader(yaml.SafeLoader):
    anchored = False

    def compose_node(self, parent: yaml.Node | None, index: object) -> yaml.Node | None:
        if getattr(self.peek_event(), "anchor", None):
            self.anchored = True
        return super().compose_node(parent, index)


def _compose(text: str) -> yaml.MappingNode:
    loader = _Loader(text)
    try:
        root = loader.get_single_node()
    except yaml.YAMLError as e:
        raise TopologyError(f"Topology is not valid YAML: {e}") from e
    finally:
        loader.dispose()
    if loader.anchored:
        raise TopologyError("Topology uses YAML anchors or aliases, refusing to edit around them")
    if not isinstance(root, yaml.MappingNode):
        raise TopologyError("Topology has no top-level mapping")
    return root


def _entry(node: yaml.Node | None, key: str) -> yaml.Node | None:
    """Mapping value under `key`, refusing duplicates (edits and loads would disagree on them)."""

    if not isinstance(node, yaml.MappingNode):
        return None
    found = [(k, v) for k, v in node.value if getattr(k, "value", None) == key]
    if len(found) > 1:
        line = found[1][0].start_mark.line + 1
        raise TopologyError(f"Duplicate {key!r} key at line {line}, edits and loads would disagree")
    return found[0][1] if found else None


def _scalar(node: yaml.Node | None, key: str) -> str | None:
    value = _entry(node, key)
    if isinstance(value, yaml.ScalarNode) and value.tag != NULL_TAG:
        return value.value
    return None


def _key_line(node: yaml.Node | None, key: str) -> int | None:
    if not isinstance(node, yaml.MappingNode):
        return None
    return next((k.start_mark.line for k, _ in node.value if getattr(k, "value", None) == key), None)


def _regions_entry(root: yaml.MappingNode) -> tuple[int, yaml.Node]:
    value = _entry(root, "regions")
    line = _key_line(root, "regions")
    if value is None or line is None:
        raise TopologyError("No top-level 'regions:' key found in topology")
    return line, value


def _block_items(value: yaml.Node | None) -> list[yaml.Node] | None:
    """Items of block sequence: `[]` for absent or bare key, `None` when not splice-editable."""

    if value is None:
        return []
    if value.tag == NULL_TAG:
        # Bare key's null is zero-width, explicit `null` token cannot be spliced under
        return [] if value.start_mark.index == value.end_mark.index else None
    if isinstance(value, yaml.SequenceNode) and not value.flow_style:
        return list(value.value)
    return None


def _spans(items: list[yaml.Node], end_line: int) -> list[tuple[yaml.Node, int, int]]:
    """Pair each sequence item with its line span, running to next item (or `end_line`)."""

    starts = [item.start_mark.line for item in items]
    return list(zip(items, starts, [*starts[1:], end_line]))


def _region_item(item: yaml.Node, start: int, end: int) -> RegionItem:
    owner = f"region {_scalar(item, 'id')!r}"
    nodes_value = _entry(item, "nodes")
    seq = _block_items(nodes_value)
    empty_flow = None
    if seq is None and nodes_value is not None and nodes_value.tag == SEQ_TAG and not nodes_value.value:
        empty_flow = (nodes_value.start_mark.line, nodes_value.start_mark.column, nodes_value.end_mark.column)
    error = None
    if isinstance(item, yaml.MappingNode) and item.flow_style:
        error = f"{owner}: must be a block mapping to edit"
    elif seq is None and empty_flow is None:
        error = f"{owner}: 'nodes:' must be a bare key or a block sequence to edit"
    if seq is None:
        seq = list(nodes_value.value) if isinstance(nodes_value, yaml.SequenceNode) else []
    strategy = _entry(item, "lb_strategy")
    nodes: tuple[NodeItem, ...] = ()
    if seq and nodes_value is not None:
        nodes = tuple(
            NodeItem(_scalar(n, "id"), _scalar(n, "hostname"), _scalar(n, "lb_role") == "backup", s, e)
            for n, s, e in _spans(seq, nodes_value.end_mark.line)
        )
    return RegionItem(
        _scalar(item, "id"),
        _scalar(item, "type"),
        _routes(item),
        nodes,
        _key_line(item, "nodes"),
        error,
        empty_flow,
        _scalar(item, "lb_fallback"),
        _key_line(item, "lb_fallback"),
        strategy.end_mark.line if strategy is not None else None,
        start,
        end,
    )


def _fallback_to_set(region: RegionItem) -> tuple[str, int] | None:
    """First primary node of balanced region, and line to write materialized lb_fallback on."""

    if region.lb_strategy_end is None or region.lb_fallback is not None or not region.nodes:
        return None
    primary = next((n for n in region.nodes if not n.backup), region.nodes[0])
    return None if primary.id is None else (primary.id, region.lb_strategy_end + 1)


def _hub_route_items(root: yaml.MappingNode) -> tuple[int | None, tuple[RouteItem, ...]]:
    """`routing.hub_routes` entries with line spans, empty when absent."""

    routing = _entry(root, "routing")
    value = _entry(routing, "hub_routes")
    items = _block_items(value)
    if items is None:
        raise TopologyError("'routing.hub_routes' must be a bare key or a block sequence to edit")
    line = _key_line(routing, "hub_routes")
    if not items or value is None:
        return line, ()
    return line, tuple(RouteItem(_scalar(i, "destination"), s, e) for i, s, e in _spans(items, value.end_mark.line))


def _int_scalar(node: yaml.Node | None, key: str) -> int | None:
    """Resolve int scalar as YAML would (handles spellings like `1_000`)."""

    raw = _scalar(node, key)
    if raw is None:
        return None
    try:
        value = yaml.safe_load(raw)
    except yaml.YAMLError:
        return None
    return value if isinstance(value, int) else None


def _routes(item: yaml.Node) -> frozenset[int]:
    routes = (_int_scalar(holder, "vless_route") for holder in (item, _entry(item, "warp")))
    return frozenset(r for r in routes if r is not None)


def _insert_at(lines: list[str], nodes: tuple[NodeItem, ...], nodes_line: int, node_id: str) -> int:
    key = _natural_key(node_id)
    earlier = [n for n in nodes if n.id is not None and _natural_key(n.id) < key]
    if earlier:
        return _append_at(lines, earlier[-1], NODE_INDENT)
    if nodes:
        _check_indent(lines, nodes[0], NODE_INDENT)
    return nodes_line + 1


def _check_indent(lines: list[str], item: RegionItem | NodeItem, indent: str) -> None:
    """Refuse to splice next to differently indented siblings."""

    if not lines[item.start].startswith(f"{indent}- "):
        raise TopologyError(
            f"Expected {len(indent)}-space indented '- id:' items to splice next to, found {lines[item.start]!r}"
        )


def _check_dash(lines: list[str], item: NodeItem | RouteItem) -> None:
    if not lines[item.start].lstrip().startswith("- "):
        raise TopologyError(f"Expected a '- ' list item to remove, found {lines[item.start]!r}")


def _append_at(lines: list[str], item: RegionItem | NodeItem, indent: str) -> int:
    _check_indent(lines, item, indent)
    return _content_end(lines, item.start, item.end)


def _content_end(lines: list[str], start: int, end: int) -> int:
    """End of `lines[start:end]` without trailing blank and comment lines, which belong to what follows."""

    while end > start and (not lines[end - 1].strip() or lines[end - 1].lstrip().startswith("#")):
        end -= 1
    return end
