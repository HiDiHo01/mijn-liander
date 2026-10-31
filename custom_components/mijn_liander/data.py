"""Validate shared connection and meter containers from the Liander API."""

from .const import SERVICE_NAME_GAS
from .gas import get_active_gas_connection


def get_mapping_list(value: object) -> list[dict[str, object]] | None:
    """Accept an explicit list of mappings without treating missing data as empty."""
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        return None
    return value


def get_connection(data: object, service_name: str | None) -> dict[str, object] | None:
    """Select active gas or the first valid electricity record, skipping bad siblings."""
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
        electricity = connections.get("elektra")
        if not isinstance(electricity, list):
            continue
        for connection in electricity:
            if isinstance(connection, dict):
                return connection
    return None


def get_first_meter(connection: dict[str, object]) -> dict[str, object] | None:
    """Validate the selected first meter independently of later sibling records."""
    meters = connection.get("meters")
    if not isinstance(meters, list) or not meters or not isinstance(meters[0], dict):
        return None
    return meters[0]
