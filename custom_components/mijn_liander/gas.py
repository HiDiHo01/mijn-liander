"""Helpers for determining whether an account has an active gas contract."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Protocol, TypeVar

from .const import SERVICE_NAME_GAS


class _ServiceEntityDescription(Protocol):
    service_name: str | None


_Description = TypeVar("_Description", bound=_ServiceEntityDescription)


def has_active_gas_contract(data: Any) -> bool:
    """Return whether any account has a gas connection with an active contract."""
    if not isinstance(data, list):
        return False

    for account in data:
        if not isinstance(account, dict):
            continue
        connections = account.get("aansluitingen")
        if not isinstance(connections, dict):
            continue
        gas_connections = connections.get("gas")
        if not isinstance(gas_connections, list):
            continue
        if any(
            isinstance(connection, dict) and connection.get("contract") is True
            for connection in gas_connections
        ):
            return True

    return False


def filter_entity_descriptions(
    descriptions: Iterable[_Description],
    data: Any,
) -> list[_Description]:
    """Include gas descriptions only when an active gas contract is present."""
    gas_available = has_active_gas_contract(data)
    return [
        description
        for description in descriptions
        if description.service_name != SERVICE_NAME_GAS or gas_available
    ]
