# AlphaESS EVCT11 MQTT Bridge

Eine performante Web-API Bridge für die AlphaESS EVCT11 Wallbox zur nahtlosen Steuerung über **MQTT**, **evcc** und **Home Assistant**.

## Features

* **Anbindung via AlphaESS Web API:** Keine lokalen Hardware-Modifikationen erforderlich.
* **evcc Kompatibilität:** Bietet alle Steuerungsendpunkte (Enable, Current, Phases, Mode).
* **Sichere Phasenumschaltung (1P/3P):** Führt bei aktiver Ladung eine automatisierte Stop-Wait-Switch-Start-Sequenz durch, um Hardwareschäden zu vermeiden.
* **Dynamisches Polling:** Polling-Intervall von 120s im Leerlauf (State A) und 15s während aktiver Sessions (State B/C).
* **On-Demand Refresh:** Sofortiges Feedback bei empfangenen Steuerbefehlen.
* **Home Assistant MQTT Auto-Discovery:** Automatische Registrierung aller relevanten Entitäten in Home Assistant.

## Konfiguration (Home Assistant Add-on)

| Option | Beschreibung | Standardwert |
| :--- | :--- | :--- |
| `ALPHAESS_USERNAME` | Benutzername (E-Mail) für AlphaESS Cloud | *Erforderlich* |
| `ALPHAESS_PASSWORD` | Passwort für AlphaESS Cloud | *Erforderlich* |
| `ALPHAESS_BASE_URL` | Cloud Endpoint URL | `https://eurcloud.alphaess.com` |
| `MQTT_BROKER` | Address des MQTT Brokers | `mqtt://homeassistant:1883` |
| `MQTT_USER` | MQTT Benutzer (falls benötigt) | *optional* |
| `MQTT_PASSWORD` | MQTT Passwort (falls benötigt) | *optional* |
| `MQTT_BASE_TOPIC` | Basis-Topic für MQTT Status & Steuerung | `evcc/chargers/alphaess` |
| `MQTT_HA_DISCOVERY` | Home Assistant Auto-Discovery aktivieren | `true` |

## MQTT Interface & evcc Integration

### Publish Topics (Status)

* `evcc/chargers/alphaess/status`: Vehicle Status (`A`, `B`, `C`, `F`)
* `evcc/chargers/alphaess/enabled`: Ladestatus (`true` / `false`)
* `evcc/chargers/alphaess/maxcurrent`: Aktuell eingestellte Stromstärke in Ampere
* `evcc/chargers/alphaess/power`: Errechnete Zielleistung in Watt

### Subscribe Topics (Steuerung)

* `evcc/chargers/alphaess/enable/set`: Ladevorgang starten/stoppen (`true` / `false`)
* `evcc/chargers/alphaess/maxcurrent/set`: Ziel-Stromstärke setzen (z. B. `6` bis `16`)
* `evcc/chargers/alphaess/phases/set`: Phasenumschaltung (`1` oder `3`)
* `evcc/chargers/alphaess/mode/set`: Lademodus setzen (`custom` oder `2`)

---

### `evcc.yaml` Konfigurationsbeispiel

```yaml
chargers:
  - name: my_alphaess_wallbox
    type: custom
    status:
      source: mqtt
      topic: evcc/chargers/alphaess/status
    enabled:
      source: mqtt
      topic: evcc/chargers/alphaess/enabled
    enable:
      source: mqtt
      topic: evcc/chargers/alphaess/enable/set
    maxcurrent:
      source: mqtt
      topic: evcc/chargers/alphaess/maxcurrent/set
    phases:
      source: mqtt
      topic: evcc/chargers/alphaess/phases/set