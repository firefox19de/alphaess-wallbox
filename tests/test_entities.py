"""Tests fuer die Home Assistant Entities (Button, Number, Select)."""
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

    def async_add_listener(self, listener, context=None):
        return lambda: None

    def async_remove_listener(self, listener):
        pass


@pytest.fixture
def mock_client():
    client = MagicMock()
    client.ev_charger_sn = "ALPHATEST123"
    client.async_set_ev_charge_current = AsyncMock(return_value=True)
    client.async_set_ev_charge_mode = AsyncMock(return_value=True)
    client.async_set_ev_phases = AsyncMock(return_value=True)
    return client


@pytest.fixture
def device_info(mock_client):
    from homeassistant.helpers.entity import DeviceInfo
    return DeviceInfo(
        identifiers={("alphaess", mock_client.ev_charger_sn)},
        name=f"Alpha ESS Charger : {mock_client.ev_charger_sn}",
        manufacturer="Alpha ESS",
        model="SMILE-EVCT11",
    )


@pytest.mark.asyncio
async def test_fetch_status_button(mock_client, device_info):
    coordinator = FakeCoordinator(mock_client)
    button = AlphaESSFetchStatusButton(coordinator, device_info, "test_entry")
    await button.async_press()
    coordinator.async_refresh.assert_called_once()


@pytest.mark.asyncio
async def test_number_entity_native_value(mock_client, device_info):
    coordinator = FakeCoordinator(mock_client, data={"chargeCurrent": 12.0})
    number = AlphaWallboxCurrentNumber(coordinator, device_info, "test_entry")
    assert number.native_value == 12.0


@pytest.mark.asyncio
async def test_number_entity_set_value_whole(mock_client, device_info):
    """Ganzzahlige Werte werden unveraendert weitergegeben."""
    coordinator = FakeCoordinator(mock_client, data={"chargeCurrent": 6.0})
    number = AlphaWallboxCurrentNumber(coordinator, device_info, "test_entry")
    number.async_write_ha_state = MagicMock()
    await number.async_set_native_value(14.0)
    mock_client.async_set_ev_charge_current.assert_called_once_with(14.0)
    coordinator.async_request_refresh.assert_called_once()


@pytest.mark.asyncio
async def test_number_entity_set_value_decimal(mock_client, device_info):
    """Dezimalwerte wie 7.4 A werden mit 0.1-Praezision weitergegeben."""
    coordinator = FakeCoordinator(mock_client, data={"chargeCurrent": 6.0})
    number = AlphaWallboxCurrentNumber(coordinator, device_info, "test_entry")
    number.async_write_ha_state = MagicMock()
    await number.async_set_native_value(7.4)
    mock_client.async_set_ev_charge_current.assert_called_once_with(7.4)
    assert coordinator.data["chargeCurrent"] == 7.4


@pytest.mark.asyncio
async def test_mode_select_current_option(mock_client, device_info):
    coordinator = FakeCoordinator(mock_client, data={"chargeMode": 1})
    select = AlphaESSModeSelect(coordinator, device_info, "test_entry")
    assert select.current_option == "Eco / Langsamladung (Nur PV)"


@pytest.mark.asyncio
async def test_mode_select_set_option(mock_client, device_info):
    coordinator = FakeCoordinator(mock_client, data={"chargeMode": 4})
    select = AlphaESSModeSelect(coordinator, device_info, "test_entry")
    select.async_write_ha_state = MagicMock()
    await select.async_select_option("Eco / Schnellladung")
    mock_client.async_set_ev_charge_mode.assert_called_once_with(3)
    coordinator.async_request_refresh.assert_called_once()


@pytest.mark.asyncio
async def test_phase_select_current_option(mock_client, device_info):
    coordinator = FakeCoordinator(mock_client, data={"obcPhase": 1})
    select = AlphaESSPhaseSelect(coordinator, device_info, "test_entry")
    assert select.current_option == "1-phasig"


@pytest.mark.asyncio
async def test_phase_select_set_option(mock_client, device_info):
    coordinator = FakeCoordinator(mock_client, data={"obcPhase": 1})
    select = AlphaESSPhaseSelect(coordinator, device_info, "test_entry")
    select.async_write_ha_state = MagicMock()
    await select.async_select_option("3-phasig")
    mock_client.async_set_ev_phases.assert_called_once_with(3)
    coordinator.async_request_refresh.assert_called_once()
