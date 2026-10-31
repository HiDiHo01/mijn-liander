"""Validate shared connection and meter containers from the Liander API."""

from .const import SERVICE_NAME_GAS
from .gas import get_active_gas_connection


def get_mapping_list(value: object) -> list[dict[str, object]] | None:
    """Accept an explicit list of mappings without treating missing data as empty."""
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        return None
    return value


def get_connection(data: object, service_name: str | None) -> dict[str, object] | None:
    """Select the active gas or first electricity connection within this entry."""
    if service_name == SERVICE_NAME_GAS:
        return get_active_gas_connection(data)
    if not isinstance(data, list):
        return None
    for account in data:
        if not isinstance(account, dict):
            continue
        connections = account.get("aansluitingen")
        if not isinstance(connections, dict):
            continue
        electricity = get_mapping_list(connections.get("elektra"))
        if electricity:
            return electricity[0]
    return None


def get_first_meter(connection: dict[str, object]) -> dict[str, object] | None:
    """Return the first meter only when the meter list has a valid shape."""
    meters = get_mapping_list(connection.get("meters"))
    return meters[0] if meters else None
