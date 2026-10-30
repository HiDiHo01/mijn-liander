"""Exercise account identity through Home Assistant's config-flow manager."""

import asyncio
from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_USER
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mijn_liander.config_flow import _validate_input
from custom_components.mijn_liander.const import DOMAIN

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


def _credentials(email_address: str) -> dict[str, object]:
    """Return synthetic credentials with a non-default request timeout."""
    return {
        CONF_USERNAME: email_address,
        CONF_PASSWORD: "test-password",
        "timeout": 8,
    }


def _add_account(
    hass: HomeAssistant, email_address: str, unique_id: str | None
) -> MockConfigEntry:
    """Register an existing account without loading its network coordinator."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title=email_address,
        unique_id=unique_id,
        data={**_credentials(email_address), "jwt_token": "old-test-token"},
    )
    config_entry.add_to_hass(hass)
    return config_entry


@pytest.fixture(name="authentication")
def authentication_fixture() -> Generator[AsyncMock]:
    """Stub remote authentication while exercising the real config-flow manager."""
    with patch(
        "custom_components.mijn_liander.config_flow._validate_input",
        return_value={"status": "success", "jwt_token": "new-test-token"},
    ) as authentication_mock:
        yield authentication_mock


@pytest.fixture(autouse=True)
def mock_setup_fixture() -> Generator[None]:
    """Prevent created config entries from making live API requests."""
    with patch("custom_components.mijn_liander.async_setup_entry", return_value=True):
        yield


@pytest.fixture(name="login_response")
def login_response_fixture() -> Generator[MagicMock]:
    """Provide a mocked HTTP response for credential validation tests."""
    with patch(
        "custom_components.mijn_liander.config_flow.aiohttp.ClientSession"
    ) as factory:
        session = MagicMock()
        response = MagicMock()
        response.json = AsyncMock()
        factory.return_value.__aenter__.return_value = session
        session.post.return_value.__aenter__.return_value = response
        yield response


async def test_multiple_email_accounts(
    hass: HomeAssistant, authentication: AsyncMock
) -> None:
    """Create separate entries for distinct email addresses without changing others."""
    created_entries = []
    for email_address in ("First@Example.com", "second@example.com"):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=_credentials(f" {email_address} "),
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == email_address
        assert result["data"] == {
            **_credentials(email_address),
            "jwt_token": "new-test-token",
        }
        assert result["result"].unique_id == email_address.casefold()
        created_entries.append(result["result"])

    await hass.async_block_till_done()
    assert len(hass.config_entries.async_entries(DOMAIN)) == 2
    assert created_entries[0].entry_id != created_entries[1].entry_id
    assert created_entries[0].data[CONF_USERNAME] == "First@Example.com"
    assert authentication.await_count == 2


@pytest.mark.parametrize(
    ("stored_email", "stored_unique_id", "submitted_email"),
    [
        ("first@example.com", "first@example.com", "first@example.com"),
        ("First@Example.COM", "First@Example.COM", " FIRST@example.com "),
        (" First@Example.COM ", "legacy-account-id", "first@example.com"),
        ("first@example.com", None, "FIRST@example.com"),
        ("first@example.com", " FIRST@example.com ", "first@example.com"),
    ],
)
async def test_duplicate_email_is_rejected(
    hass: HomeAssistant,
    authentication: AsyncMock,
    stored_email: str,
    stored_unique_id: str | None,
    submitted_email: str,
) -> None:
    """Reject equivalent email addresses, preserving legacy entry identities."""
    existing_entry = _add_account(hass, stored_email, stored_unique_id)
    original_data = dict(existing_entry.data)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data=_credentials(submitted_email),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert hass.config_entries.async_entries(DOMAIN) == [existing_entry]
    assert existing_entry.unique_id == stored_unique_id
    assert dict(existing_entry.data) == original_data
    authentication.assert_not_awaited()


async def test_concurrent_duplicate_email_is_rejected(
    hass: HomeAssistant, authentication: AsyncMock
) -> None:
    """Reserve the normalized identity before an outstanding login completes."""
    login_started = asyncio.Event()
    finish_login = asyncio.Event()

    async def delayed_login(username: str, password: str) -> dict[str, str]:
        """Pause authentication so a second flow can submit the same account."""
        login_started.set()
        await finish_login.wait()
        return {"status": "success", "jwt_token": "new-test-token"}

    authentication.side_effect = delayed_login
    first_flow = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    second_flow = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    pending_login = hass.async_create_task(
        hass.config_entries.flow.async_configure(
            first_flow["flow_id"], _credentials("first@example.com")
        )
    )
    try:
        await login_started.wait()
        duplicate_result = await hass.config_entries.flow.async_configure(
            second_flow["flow_id"], _credentials(" FIRST@example.com ")
        )
    finally:
        finish_login.set()

    first_result = await pending_login
    await hass.async_block_till_done()
    assert duplicate_result["type"] is FlowResultType.ABORT
    assert duplicate_result["reason"] == "already_in_progress"
    assert first_result["type"] is FlowResultType.CREATE_ENTRY
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    authentication.assert_awaited_once()


@pytest.mark.parametrize("invalid_email", ["", "   ", "missing-at-sign", 123, None])
async def test_invalid_email_is_rejected(
    hass: HomeAssistant, authentication: AsyncMock, invalid_email: object
) -> None:
    """Reject invalid email input before authentication or entry creation."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={**_credentials("first@example.com"), CONF_USERNAME: invalid_email},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_input"}
    assert not hass.config_entries.async_entries(DOMAIN)
    authentication.assert_not_awaited()


@pytest.mark.parametrize(
    ("login_error", "expected_error"),
    [(TimeoutError(), "cannot_connect"), (RuntimeError("test failure"), "unknown")],
)
async def test_login_exceptions_do_not_create_accounts(
    hass: HomeAssistant,
    authentication: AsyncMock,
    login_error: Exception,
    expected_error: str,
) -> None:
    """Keep connection and unexpected errors in the form without creating entries."""
    authentication.side_effect = login_error
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data=_credentials("first@example.com"),
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}
    assert not hass.config_entries.async_entries(DOMAIN)


async def test_reauth_initializes_with_stored_entry_data(
    hass: HomeAssistant, authentication: AsyncMock
) -> None:
    """Show an error-free confirmation form when Home Assistant supplies stored tokens."""
    existing_entry = _add_account(hass, "first@example.com", "first@example.com")

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_REAUTH, "entry_id": existing_entry.entry_id},
        data=dict(existing_entry.data),
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {}
    assert existing_entry.data["jwt_token"] == "old-test-token"
    authentication.assert_not_awaited()


@pytest.mark.parametrize(
    "legacy_unique_id", ["First@Example.com", "legacy-account-id", None]
)
async def test_reauth_preserves_account_identity(
    hass: HomeAssistant, authentication: AsyncMock, legacy_unique_id: str | None
) -> None:
    """Refresh only the same account and preserve existing entry and entity IDs."""
    existing_entry = _add_account(hass, "First@Example.com", legacy_unique_id)
    other_entry = _add_account(hass, "second@example.com", "second@example.com")
    other_data = dict(other_entry.data)

    with patch.object(
        hass.config_entries, "async_reload", return_value=True
    ) as reload_mock:
        initialized_flow = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_REAUTH, "entry_id": existing_entry.entry_id},
            data=dict(existing_entry.data),
        )
        result = await hass.config_entries.flow.async_configure(
            initialized_flow["flow_id"], _credentials(" FIRST@example.com ")
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert existing_entry.unique_id == legacy_unique_id
    assert existing_entry.data == {
        **_credentials("FIRST@example.com"),
        "jwt_token": "new-test-token",
    }
    assert dict(other_entry.data) == other_data
    assert len(hass.config_entries.async_entries(DOMAIN)) == 2
    authentication.assert_awaited_once_with("FIRST@example.com", "test-password")
    reload_mock.assert_awaited_once_with(existing_entry.entry_id)


@pytest.mark.parametrize("different_email", ["second@example.com", "new@example.com"])
async def test_reauth_cannot_switch_accounts(
    hass: HomeAssistant, authentication: AsyncMock, different_email: str
) -> None:
    """Prevent reauthentication from duplicating another account or replacing data."""
    existing_entry = _add_account(hass, "first@example.com", "first@example.com")
    _add_account(hass, "second@example.com", "second@example.com")
    original_data = dict(existing_entry.data)

    with patch.object(
        hass.config_entries, "async_reload", return_value=True
    ) as reload_mock:
        initialized_flow = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_REAUTH, "entry_id": existing_entry.entry_id},
            data=dict(existing_entry.data),
        )
        result = await hass.config_entries.flow.async_configure(
            initialized_flow["flow_id"], _credentials(different_email)
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "wrong_account"}
    assert dict(existing_entry.data) == original_data
    assert existing_entry.unique_id == "first@example.com"
    authentication.assert_not_awaited()
    reload_mock.assert_not_awaited()


@pytest.mark.parametrize(
    "invalid_payload", [None, [], {}, {"jwt": None}, {"jwt": 123}, {"jwt": " "}]
)
async def test_invalid_login_payload_is_rejected(
    login_response: MagicMock, invalid_payload: object
) -> None:
    """Require a mapping containing a non-empty string token before creating accounts."""
    login_response.json.return_value = invalid_payload

    result = await _validate_input("first@example.com", "test-password")

    assert result == {"status": "error", "error": "invalid_auth"}


async def test_login_does_not_log_credentials(
    login_response: MagicMock, caplog: pytest.LogCaptureFixture
) -> None:
    """Keep email addresses, passwords, and tokens out of authentication logs."""
    login_response.json.return_value = {"jwt": "private-test-token"}

    with caplog.at_level("DEBUG", logger="custom_components.mijn_liander.config_flow"):
        result = await _validate_input("private@example.com", "private-test-password")

    assert result == {"status": "success", "jwt_token": "private-test-token"}
    for sensitive_value in (
        "private@example.com",
        "private-test-password",
        "private-test-token",
    ):
        assert sensitive_value not in caplog.text
