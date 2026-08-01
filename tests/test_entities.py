"""Tests for the Home Assistant entities (Button, Number, Select)."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from custom_components.alphaess_wallbox.button import AlphaESSFetchStatusButton
from custom_components.alphaess_wallbox.number import AlphaWallboxCurrentNumber
from custom_components.alphaess_wallbox.select import AlphaESSModeSelect, AlphaESSPhaseSelect

@pytest.fixture
def mock_api():
    """Stellt einen gemockten API-Client für die Tests bereit."""
    api = MagicMock()
    api.get_wallbox_status = AsyncMock()
    api.set_charging_current = AsyncMock(return_value=True)
    api.set_charge_mode = AsyncMock(return_value=True)
    api.set_phases = AsyncMock(return_value=True)
    return api

@pytest.fixture
def mock_device_info():
    """Stellt minimale Device-Info-Strukturen bereit."""
    return {"identifiers": {("alphaess_wallbox", "ALPHATEST123")}}

@pytest.mark.asyncio
async def test_fetch_status_button(mock_api, mock_device_info):
    """Testet, ob der Button-Druck die Status-Abfrage der API auslöst."""
    button = AlphaESSFetchStatusButton(mock_api, mock_device_info, "test_entry")
    
    await button.async_press()
    
    mock_api.get_wallbox_status.assert_called_once()

@pytest.mark.asyncio
async def test_number_entity(mock_api, mock_device_info):
    """Testet das Lesen und Setzen der Stromstärke."""
    # 1. Test: Lesen der Werte
    mock_api.get_wallbox_status.return_value = {"max_current": 12}
    number = AlphaWallboxCurrentNumber(mock_api, mock_device_info, "test_entry")
    number.async_write_ha_state = MagicMock()
    
    await number.async_update()
    assert number._attr_native_value == 12

    # 2. Test: Setzen der Werte
    await number.async_set_native_value(14)
    
    mock_api.set_charging_current.assert_called_once_with(14)
    assert number._attr_native_value == 14
    number.async_write_ha_state.assert_called_once()

@pytest.mark.asyncio
async def test_mode_select_entity(mock_api, mock_device_info):
    """Testet das Mapping und Setzen der Lademodi."""
    # Mode 1 entspricht "Eco / Langsamladung (Nur PV)" in const/map
    mock_api.get_wallbox_status.return_value = {"charging_mode": 1}
    select = AlphaESSModeSelect(mock_api, mock_device_info, "test_entry")
    select.async_write_ha_state = MagicMock()
    
    # 1. Update Test
    await select.async_update()
    assert select._attr_current_option == "Eco / Langsamladung (Nur PV)"

    # 2. Set Test (3 entspricht "Eco / Schnellladung")
    await select.async_select_option("Eco / Schnellladung")
    mock_api.set_charge_mode.assert_called_once_with(3)
    assert select._attr_current_option == "Eco / Schnellladung"
    select.async_write_ha_state.assert_called_once()

@pytest.mark.asyncio
async def test_phase_select_entity(mock_api, mock_device_info):
    """Testet das Mapping und Setzen der Phasen."""
    mock_api.get_wallbox_status.return_value = {"phase": 1}
    select = AlphaESSPhaseSelect(mock_api, mock_device_info, "test_entry")
    select.async_write_ha_state = MagicMock()
    
    # 1. Update Test
    await select.async_update()
    assert select._attr_current_option == "1-phasig"

    # 2. Set Test
    await select.async_select_option("3-phasig")
    mock_api.set_phases.assert_called_once_with(3)
    assert select._attr_current_option == "3-phasig"
    select.async_write_ha_state.assert_called_once()