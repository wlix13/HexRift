from pydantic import BaseModel, Field, model_validator

from hexrift.components.schema.models.defaults import DefaultsConfig
from hexrift.components.schema.models.global_ import GlobalConfig
from hexrift.components.schema.models.groups import Group
from hexrift.components.schema.models.regions import Region
from hexrift.components.schema.models.routing import RoutingConfig
from hexrift.components.schema.models.users import User
from hexrift.constants import SPECIAL_DESTINATIONS, RegionType


class ConglomerateConfig(BaseModel):
    global_: GlobalConfig = Field(alias="global")
    defaults: DefaultsConfig
    groups: list[Group]
    users: list[User]
    routing: RoutingConfig
    regions: list[Region]

    model_config = {"populate_by_name": True}

    @model_validator(mode="after")
    def _validate_references(self) -> "ConglomerateConfig":
        group_ids = {g.id for g in self.groups}
        region_ids = {r.id for r in self.regions}
        node_ids: set[str] = set()

        # Unique region IDs
        if len(region_ids) != len(self.regions):
            seen: set[str] = set()
            for r in self.regions:
                if r.id in seen:
                    raise ValueError(f"Duplicate region id: {r.id!r}")
                seen.add(r.id)

        # Unique node IDs across all regions; exit regions need vless_route + reality
        seen_vless_routes: dict[int, str] = {}  # route → region id
        for region in self.regions:
            for node in region.nodes:
                if node.id in node_ids:
                    raise ValueError(f"Duplicate node id: {node.id!r}")
                node_ids.add(node.id)
            if region.type == RegionType.EXIT:
                if region.vless_route is None:
                    raise ValueError(f"Exit region {region.id!r} must have vless_route")
                if region.vless_route in seen_vless_routes:
                    raise ValueError(
                        f"Duplicate vless_route {region.vless_route} in region {region.id!r}"
                        f" (already used by {seen_vless_routes[region.vless_route]!r})"
                    )
                seen_vless_routes[region.vless_route] = region.id
                if region.warp is not None:
                    if region.warp.vless_route in seen_vless_routes:
                        raise ValueError(
                            f"Duplicate warp vless_route {region.warp.vless_route} in region {region.id!r}"
                            f" (already used by {seen_vless_routes[region.warp.vless_route]!r})"
                        )
                    seen_vless_routes[region.warp.vless_route] = f"{region.id}(warp)"
                for node in region.nodes:
                    if node.reality is None:
                        raise ValueError(f"Exit node {node.id!r} in region {region.id!r} must have reality config")
            if region.lb_fallback is not None:
                region_node_ids = {n.id for n in region.nodes}
                if region.lb_fallback not in region_node_ids:
                    raise ValueError(
                        f"lb_fallback {region.lb_fallback!r} in region {region.id!r} is not a node in that region"
                    )

        # Unique group IDs
        if len(group_ids) != len(self.groups):
            seen_g: set[str] = set()
            for g in self.groups:
                if g.id in seen_g:
                    raise ValueError(f"Duplicate group id: {g.id!r}")
                seen_g.add(g.id)

        # Unique usernames
        usernames: set[str] = set()
        for user in self.users:
            if user.username in usernames:
                raise ValueError(f"Duplicate username: {user.username!r}")
            usernames.add(user.username)
            if user.group not in group_ids:
                raise ValueError(f"User {user.username!r} references unknown group {user.group!r}")

        # hub_default references valid region
        hub_default = self.routing.hub_default
        if hub_default not in region_ids:
            raise ValueError(f"hub_default {hub_default!r} is not a known region")

        # hub_routes destinations
        valid_destinations = SPECIAL_DESTINATIONS | region_ids | node_ids
        for route in self.routing.hub_routes:
            if route.destination not in valid_destinations:
                raise ValueError(f"hub_route destination {route.destination!r} is unknown")
            for u in route.users or []:
                if u not in usernames:
                    raise ValueError(f"hub_route user {u!r} is not a known user")
            for u in route.proxy_users or []:
                if u not in usernames:
                    raise ValueError(f"hub_route proxy_user {u!r} is not a known user")

        return self
