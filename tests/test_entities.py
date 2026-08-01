"""Tests for the Home Assistant entities (Button, Number, Select)."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from custom_components.alphaess_wallbox.button import AlphaESSFetchStatusButton
from custom_components.alphaess_wallbox.number import AlphaWallboxCurrentNumber
from custom_components.alphaess_wallbox.select import AlphaESSModeSelect, AlphaESSPhaseSelect


class FakeCoordinator:
    def __init__(self, client, data=None):
        self.client = client
        self.data = data or {}
        self.async_refresh = AsyncMock()
        self.async_request_refresh = AsyncMock()

    def async_add_listener(self, listener):
        return None

    def async_remove_listener(self, listener):
        return None


@pytest.fixture
def mock_api():
    """Provide a mocked API client for entity tests."""
    api = MagicMock()
    api.get_wallbox_status = AsyncMock()
    api.set_charging_current = AsyncMock(return_value=True)
    api.set_charge_mode = AsyncMock(return_value=True)
    api.set_phases = AsyncMock(return_value=True)
    return api


@pytest.fixture
def mock_device_info():
    """Provide minimal device info structure."""
    return {"identifiers": {("alphaess_wallbox", "ALPHATEST123")}}


@pytest.mark.asyncio
async def test_fetch_status_button(mock_api, mock_device_info):
    """Verify button press triggers coordinator refresh."""
    coordinator = FakeCoordinator(mock_api)
    button = AlphaESSFetchStatusButton(
        coordinator, mock_device_info, "test_entry")

    await button.async_press()

    coordinator.async_refresh.assert_called_once()


@pytest.mark.asyncio
async def test_number_entity(mock_api, mock_device_info):
    """Verify number entity reads and writes max current."""
    coordinator = FakeCoordinator(mock_api, data={"max_current": 12})
    number = AlphaWallboxCurrentNumber(
        coordinator, mock_device_info, "test_entry")
    number.async_write_ha_state = MagicMock()

    assert number.native_value == 12

    await number.async_set_native_value(14)

    mock_api.set_charging_current.assert_called_once_with(14)
    assert number.native_value == 14
    number.async_write_ha_state.assert_called_once()
    coordinator.async_request_refresh.assert_called_once()


@pytest.mark.asyncio
async def test_mode_select_entity(mock_api, mock_device_info):
    """Verify mode select maps and sets the charging mode."""
    coordinator = FakeCoordinator(mock_api, data={"charging_mode": 1})
    select = AlphaESSModeSelect(coordinator, mock_device_info, "test_entry")
    select.async_write_ha_state = MagicMock()

    assert select.current_option == "Eco / Langsamladung (Nur PV)"

    await select.async_select_option("Eco / Schnellladung")

    mock_api.set_charge_mode.assert_called_once_with(3)
    assert select.current_option == "Eco / Schnellladung"
    select.async_write_ha_state.assert_called_once()
    coordinator.async_request_refresh.assert_called_once()


@pytest.mark.asyncio
async def test_phase_select_entity(mock_api, mock_device_info):
    """Verify phase select maps and sets the phase count."""
    coordinator = FakeCoordinator(mock_api, data={"phase": 1})
    select = AlphaESSPhaseSelect(coordinator, mock_device_info, "test_entry")
    select.async_write_ha_state = MagicMock()

    assert select.current_option == "1-phasig"

    await select.async_select_option("3-phasig")

    mock_api.set_phases.assert_called_once_with(3)
    assert select.current_option == "3-phasig"
    select.async_write_ha_state.assert_called_once()
    coordinator.async_request_refresh.assert_called_once()
