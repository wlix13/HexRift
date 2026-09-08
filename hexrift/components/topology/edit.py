from __future__ import annotations

import json
import re
from dataclasses import dataclass

import yaml
from pydantic import BaseModel, ValidationError

from hexrift.components.schema.models.regions import Node, Region
from hexrift.errors import TopologyError


REGION_INDENT = "  "
NODE_INDENT = "      "
NULL_TAG = "tag:yaml.org,2002:null"


def _natural_key(value: str) -> list[int | str]:
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", value)]


def spec[M: BaseModel](model: type[M], **fields: object) -> M:
    """Validate `fields` as schema `model`, reporting what the schema would reject as one error."""

    try:
        return model.model_validate(fields)
    except ValidationError as e:
        problems = ", ".join(f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in e.errors())
        raise TopologyError(f"Invalid {model.__name__} {problems}") from e


def _scalar_text(value: str, flow: bool = False) -> str:
    """Quote values YAML would not read back as identical plain strings (`no`, `123`, `/a:`, `a, b` inside `[]`)."""

    doc, want = (f"[ {value} ]", [value]) if flow else (value, value)
    try:
        if yaml.safe_load(doc) == want:
            return value
    except yaml.YAMLError:
        pass
    return json.dumps(value, ensure_ascii=False)


@dataclass(frozen=True)
class NodeItem:
    id: str | None
    hostname: str | None
    backup: bool
    start: int
    end: int


@dataclass(frozen=True, kw_only=True)
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
    hysteria: bool
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
    region: Region
    node: Node
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


def node_lines(node: Node) -> list[str]:
    return _item(_fields(node), NODE_INDENT)


def region_lines(region: Region, node: Node) -> list[str]:
    return _item(_fields(region.model_copy(update={"nodes": [node]})), REGION_INDENT)


def _fields(model: BaseModel) -> dict[str, object]:
    """Explicitly set, non-null fields only, so schema defaults never land in the file."""

    return model.model_dump(mode="json", exclude_unset=True, exclude_none=True)


def _block(mapping: dict[str, object], indent: str) -> list[str]:
    lines: list[str] = []
    for key, value in mapping.items():
        if isinstance(value, dict):
            lines.append(f"{indent}{key}:")
            lines.extend(_block(value, indent + "  "))
        elif isinstance(value, list) and value and isinstance(value[0], dict):
            lines.append(f"{indent}{key}:")
            for item in value:
                lines.extend(_item(item, indent + "  "))
        elif isinstance(value, list):
            lines.append(f"{indent}{key}: [{', '.join(_yaml_scalar(v, flow=True) for v in value)}]")
        else:
            lines.append(f"{indent}{key}: {_yaml_scalar(value)}")
    return lines


def _item(mapping: dict[str, object], indent: str) -> list[str]:
    """Block sequence item, `- ` on first line and rest indented under it."""

    first, *rest = _block(mapping, indent + "  ")
    return [f"{indent}- {first.lstrip()}", *rest]


def _yaml_scalar(value: object, flow: bool = False) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    return _scalar_text(str(value), flow)


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
        self._empty_flow_regions = _empty_flow(regions_value)
        spans = _spans(self._lines, regions_value, items)
        self.regions = tuple(_region_item(self._lines, item, s, e) for item, s, e in spans)
        self.aphelion_domain = _scalar(_entry(root, "global"), "aphelion_domain")
        self._hub_routes_line, self._hub_routes, self._hub_routes_error = _hub_route_items(self._lines, root)

    def region(self, region_id: str) -> RegionItem | None:
        return next((r for r in self.regions if r.id == region_id), None)

    def has_node(self, node_id: str) -> bool:
        return any(n.id == node_id for r in self.regions for n in r.nodes)

    @property
    def used_vless_routes(self) -> set[int]:
        return {route for r in self.regions for route in r.vless_routes}

    def check_add(self, region: Region) -> RegionItem | None:
        """Region to add under, `None` when it has to be created, refusing mismatched type or unsplicable nodes."""

        existing = self.region(region.id)
        if existing is None:
            return None
        if existing.type != region.type:
            raise TopologyError(
                f"Region {region.id!r} has type '{existing.type}', refusing to add a '{region.type}' node to it"
            )
        if existing.nodes_error is not None:
            raise TopologyError(existing.nodes_error)
        return existing

    def add_node(self, region: Region, node: Node) -> AddEdit:
        """Add `node` to `region`, creating missing region at end of section."""

        if self.has_node(node.id):
            raise TopologyError(f"Node {node.id!r} is already in the topology")
        lines = list(self._lines)
        existing = self.check_add(region)
        if existing is None:
            block = region_lines(region, node)
            if self.regions:
                at = _append_at(lines, self.regions[-1], REGION_INDENT)
                block = ["", *block]
            else:
                _strip_flow(lines, self._empty_flow_regions)
                at = self._regions_line + 1
            lines[at:at] = block
            return AddEdit(self._render(lines), region, node, created=True)

        _strip_flow(lines, existing.empty_flow_nodes)
        at = _insert_at(lines, existing, node.id)
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
        if self._hub_routes_error is not None:
            raise TopologyError(self._hub_routes_error)
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
    """Items of block sequence: `[]` for absent, bare key or `[]`, `None` when not splice-editable."""

    if value is None:
        return []
    if value.tag == NULL_TAG:
        # Bare key's null is zero-width, explicit `null` token cannot be spliced under
        return [] if value.start_mark.index == value.end_mark.index else None
    if isinstance(value, yaml.SequenceNode) and (not value.flow_style or not value.value):
        return list(value.value)
    return None


def _empty_flow(value: yaml.Node | None) -> tuple[int, int, int] | None:
    """Row and column span of an empty `[]`, stripped before first splice under its key."""

    if isinstance(value, yaml.SequenceNode) and value.flow_style and not value.value:
        return _flow_span(value)
    return None


def _flow_span(node: yaml.Node) -> tuple[int, int, int]:
    return node.start_mark.line, node.start_mark.column, node.end_mark.column


def _strip_flow(lines: list[str], splice: tuple[int, int, int] | None) -> None:
    if splice is not None:
        row, first, last = splice
        lines[row] = (lines[row][:first] + lines[row][last:]).rstrip()


def _spans(lines: list[str], seq: yaml.Node, items: list[yaml.Node]) -> list[tuple[yaml.Node, int, int]]:
    """Pair each sequence item with its line span, from its `-` line to next item's (or sequence end)."""

    starts = []
    for i, item in enumerate(items):
        lower = seq.start_mark.line if i == 0 else items[i - 1].start_mark.line + 1
        starts.append(_dash_line(lines, seq.start_mark.column, min(lower, item.start_mark.line), item.start_mark.line))
    return list(zip(items, starts, [*starts[1:], seq.end_mark.line]))


def _dash_line(lines: list[str], column: int, lower: int, upper: int) -> int:
    """Line of item's `-` at sequence `column`, scanning up from its first key line to `lower`."""

    for row in range(upper, lower - 1, -1):
        if lines[row][column : column + 1] == "-" and not lines[row][:column].strip():
            return row
    return upper


def _region_item(lines: list[str], item: yaml.Node, start: int, end: int) -> RegionItem:
    owner = f"region {_scalar(item, 'id')!r}"
    nodes_value = _entry(item, "nodes")
    seq = _block_items(nodes_value)
    error = None
    if isinstance(item, yaml.MappingNode) and item.flow_style:
        error = f"{owner}: must be a block mapping to edit"
    elif seq is None:
        error = f"{owner}: 'nodes:' must be a bare key or a block sequence to edit"
    if seq is None:
        seq = list(nodes_value.value) if isinstance(nodes_value, yaml.SequenceNode) else []
    strategy = _entry(item, "lb_strategy") if _scalar(item, "lb_strategy") is not None else None
    nodes: tuple[NodeItem, ...] = ()
    if seq and nodes_value is not None:
        nodes = tuple(
            NodeItem(_scalar(n, "id"), _scalar(n, "hostname"), _scalar(n, "lb_role") == "backup", s, e)
            for n, s, e in _spans(lines, nodes_value, seq)
        )
    return RegionItem(
        id=_scalar(item, "id"),
        type=_scalar(item, "type"),
        vless_routes=_routes(item),
        nodes=nodes,
        nodes_line=_key_line(item, "nodes"),
        nodes_error=error,
        empty_flow_nodes=_empty_flow(nodes_value),
        lb_fallback=_scalar(item, "lb_fallback"),
        lb_fallback_line=_key_line(item, "lb_fallback"),
        lb_strategy_end=strategy.end_mark.line if strategy is not None else None,
        hysteria=_scalar(item, "protocol") == "hysteria" or _entry(item, "hysteria") is not None,
        start=start,
        end=end,
    )


def _fallback_to_set(region: RegionItem) -> tuple[str, int] | None:
    """First primary node of balanced region, and line to write materialized lb_fallback on."""

    if region.lb_strategy_end is None or region.lb_fallback_line is not None or not region.nodes:
        return None
    primary = next((n for n in region.nodes if not n.backup), region.nodes[0])
    return None if primary.id is None else (primary.id, region.lb_strategy_end + 1)


def _hub_route_items(lines: list[str], root: yaml.MappingNode) -> tuple[int | None, tuple[RouteItem, ...], str | None]:
    """`routing.hub_routes` entries with line spans, empty when absent, plus error refusing route edits."""

    routing = _entry(root, "routing")
    value = _entry(routing, "hub_routes")
    line = _key_line(routing, "hub_routes")
    items = _block_items(value)
    if items is None:
        return line, (), "'routing.hub_routes' must be a bare key or a block sequence to edit"
    if not items or value is None:
        return line, (), None
    return line, tuple(RouteItem(_scalar(i, "destination"), s, e) for i, s, e in _spans(lines, value, items)), None


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


def _insert_at(lines: list[str], region: RegionItem, node_id: str) -> int:
    if region.nodes_line is None:
        raise TopologyError(f"Region {region.id!r} has no 'nodes:' key to add under")
    key = _natural_key(node_id)
    earlier = [n for n in region.nodes if n.id is not None and _natural_key(n.id) < key]
    if earlier:
        return _append_at(lines, earlier[-1], NODE_INDENT)
    if region.nodes:
        _check_indent(lines, region.nodes[0], NODE_INDENT)
    return region.nodes_line + 1


def _is_dash(line: str, indent: str) -> bool:
    rest = line.removeprefix(f"{indent}-")
    return rest != line and (not rest or rest[0].isspace())


def _check_indent(lines: list[str], item: RegionItem | NodeItem, indent: str) -> None:
    """Refuse to splice next to differently indented siblings."""

    if not _is_dash(lines[item.start], indent):
        raise TopologyError(
            f"Expected {len(indent)}-space indented '- id:' items to splice next to, found {lines[item.start]!r}"
        )


def _check_dash(lines: list[str], item: NodeItem | RouteItem) -> None:
    if not _is_dash(lines[item.start].lstrip(), ""):
        raise TopologyError(f"Expected a '- ' list item to remove, found {lines[item.start]!r}")


def _append_at(lines: list[str], item: RegionItem | NodeItem, indent: str) -> int:
    _check_indent(lines, item, indent)
    return _content_end(lines, item.start, item.end)


def _content_end(lines: list[str], start: int, end: int) -> int:
    """End of `lines[start:end]` without trailing blank and comment lines, which belong to what follows."""

    while end > start and (not lines[end - 1].strip() or lines[end - 1].lstrip().startswith("#")):
        end -= 1
    return end
