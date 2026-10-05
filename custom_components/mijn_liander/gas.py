"""Helpers for determining whether an account has an active gas contract."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Protocol

from .const import SERVICE_NAME_GAS


class _ServiceEntityDescription(Protocol):
    service_name: str | None


def get_active_gas_connection(data: Any) -> dict[str, Any] | None:
    """Return the first gas connection with an active contract."""
    if not isinstance(data, list):
        return None

    for account in data:
        if not isinstance(account, dict):
            continue
        connections = account.get("aansluitingen")
        if not isinstance(connections, dict):
            continue
        gas_connections = connections.get("gas")
        if not isinstance(gas_connections, list):
            continue
        for connection in gas_connections:
            if isinstance(connection, dict) and connection.get("contract") is True:
                return connection

    return None


def has_active_gas_contract(data: Any) -> bool:
    """Return whether any account has a gas connection with an active contract."""
    return get_active_gas_connection(data) is not None


def filter_entity_descriptions[Description: _ServiceEntityDescription](
    descriptions: Iterable[Description],
    data: Any,
) -> list[Description]:
    """Include gas descriptions only when an active gas contract is present."""
    gas_available = has_active_gas_contract(data)
    return [
        description
        for description in descriptions
        if description.service_name != SERVICE_NAME_GAS or gas_available
    ]
