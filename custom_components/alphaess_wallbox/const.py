"""Konstanten für die AlphaESS Wallbox Integration."""

from homeassistant.helpers.entity import DeviceInfo

DOMAIN = "alphaess_wallbox"
DEFAULT_BASE_URL = "https://platform-eur.alphaess.com"


def build_device_info(ev_charger_sn: str) -> DeviceInfo:
    """Erstellt ein einheitliches DeviceInfo-Objekt für alle Plattform-Entities."""
    return DeviceInfo(
        identifiers={(DOMAIN, ev_charger_sn)},
        name=f"Alpha ESS Charger : {ev_charger_sn}",
        manufacturer="Alpha ESS",
        model="SMILE-EVCT11",
    )