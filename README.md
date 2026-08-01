# AlphaESS Wallbox Control (Native Home Assistant Integration)

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/default)

Erweiterte Steuerungs-Integration für die **AlphaESS EVCT11 Wallbox** in Home Assistant via AlphaESS Web-API.

Diese Integration dient als **Ergänzung** zur offiziellen OpenAPI-Integration (z. B. von CharlesGillanders), um Parameter wie **Maximalstrom, Phasenumschaltung und Lademodus** zu steuern, die über die offizielle OpenAPI von AlphaESS nicht schreibbar sind.

---

## 💡 Das Hybrid-Konzept (OpenAPI + Web-API)

Um nicht in API Rate-Limits der Web-Cloud zu laufen und gleichzeitig maximale Stabilität bei Lade-Start/Stop zu garantieren, nutzt dieses Setup einen **Hybrid-Ansatz**:

1. **Lesen & Lade-Freigabe (OpenAPI):** Statuswerte, Ladeleistung sowie Start/Stop-Signale laufen limitfrei über die Standard-OpenAPI.
2. **Parameter-Steuerung (Web-API):** Diese Custom Component übernimmt exklusiv das Schreiben von Phasenzahl, Ampere-Limit und Lademodus über die AlphaESS Web-API.

```text
┌────────────────┐        MQTT         ┌────────────────────────┐
│      EVCC      │ ──────────────────> │ evcc_bridge Automation │
└────────────────┘                     └───────────┬────────────┘
                                                   │
                         ┌─────────────────────────┴────────────────────────┐
                         │                                                  │
                         ▼                                                  ▼
      ┌─────────────────────────────────────┐            ┌───────────────────────────────────┐
      │     Charles' Integration (OpenAPI)  │            │ AlphaESS Wallbox Control (Web-API)│
      ├─────────────────────────────────────┤            ├───────────────────────────────────┤
      │ • Start/Stop Charging Buttons       │            │ • EV Charger Max Current Setting  │
      │ • Can Start/Stop Binary Sensors     │            │ • EV Charger Phases               │
      │ • EV Charger Status Raw / Power     │            │ • EV Charger Charge Mode          │
      └─────────────────────────────────────┘            └───────────────────────────────────┘
```

## 🚀 Features

* **Direkte Web-API Anbindung:**
* **Setup via UI:** Bequeme Einrichtung über den Home Assistant Config Flow.
* **Entitäten:**
  * `number.ev_charger_max_current_setting`: Steuerung der Ladeleistung (6 A – 16 A).
  * `select.ev_charger_phases`: Phasenumschaltung (`1-phasig` / `3-phasig`).
  * `select.ev_charger_charge_mode`: Lademodus (PV-Logiken / Custom EVCC-Steuerung).

---

## ⚙️ Installation via HACS

1. In **HACS** oben rechts auf die 3 Punkte klicken -> **Benutzerdefinierte Repositories**.
2. URL hinzufügen: `https://github.com/firefox19de/alphaess-wallbox`
3. Kategorie: **Integration**.
4. Auf **Herunterladen** klicken und Home Assistant neu starten.
5. Unter **Einstellungen -> Geräte & Dienste -> Integration hinzufügen** nach `AlphaESS Wallbox Control` suchen.

---

## 🔌 EVCC Integration (Beispiel)

Falls du **EVCC** nutzt, kannst du deine Wallbox via MQTT in EVCC als benutzerdefiniertes Ladepunkt-Device anbinden:

### EVCC `evcc.yaml` (Auszug)
```yaml
chargers:
  - name: alphaess_wallbox
    type: custom
    status:
      source: mqtt
      topic: ha_bridge/charger/status
    enabled:
      source: mqtt
      topic: ha_bridge/charger/enabled
    enable:
      source: mqtt
      topic: ha_bridge/charger/enable/set
      payload: ${enable}
    maxcurrent:
      source: mqtt
      topic: ha_bridge/charger/maxcurrent/set
    phases1p3p:
      source: mqtt
      topic: ha_bridge/charger/phases/set
    currents:
      - source: mqtt
        topic: ha_bridge/charger/current_calculated
      - source: mqtt
        topic: ha_bridge/charger/current_calculated
      - source: mqtt
        topic: ha_bridge/charger/current_calculated
```

Die Übersetzung der MQTT-Topics an die OpenAPI- und Web-API-Entitäten erfolgt über eine einfache Automation (`evcc_bridge.yaml`) in Home Assistant.

---

## ⚠️ Disclaimer

Dieses Projekt ist eine inoffizielle Community-Integration. Es besteht keinerlei Verbindung zur Alpha ESS Co., Ltd. Die Nutzung erfolgt auf eigene Verantwortung.
