"""Collision test request normalization rules."""

from __future__ import annotations

from typing import Any


ASSET_ROLE_PLACEMENT_MODES = {
    "furniture": "replace-table",
    "prop": "replace-box",
}


def normalize_collision_request(
    request: dict[str, Any],
    *,
    explicit_fields: set[str] | None = None,
) -> dict[str, Any]:
    normalized = dict(request)
    asset_role = normalized.get("asset_role")
    if asset_role is None:
        normalized.pop("asset_role", None)
        return normalized
    if asset_role not in ASSET_ROLE_PLACEMENT_MODES:
        raise ValueError(f"Unsupported asset_role: {asset_role}")

    placement_mode = ASSET_ROLE_PLACEMENT_MODES[str(asset_role)]
    caller_set_placement_mode = (
        "placement_mode" in explicit_fields if explicit_fields is not None else "placement_mode" in normalized
    )
    if caller_set_placement_mode and normalized.get("placement_mode") not in {None, placement_mode}:
        raise ValueError(f"asset_role={asset_role} requires placement_mode={placement_mode}")

    normalized["placement_mode"] = placement_mode
    normalized["hit_mode"] = "top-drop"
    return normalized
