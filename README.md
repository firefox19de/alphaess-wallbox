# AlphaESS EVCT11 MQTT Bridge

Eine performante Web-API Bridge für die AlphaESS EVCT11 Wallbox zur nahtlosen Steuerung über **MQTT**, **evcc** und **Home Assistant**.

## Features

* **Anbindung via AlphaESS Web API:** Keine lokalen Hardware-Modifikationen erforderlich.
* **evcc Kompatibilität:** Bietet alle Steuerungsendpunkte (Enable, Current, Phases, Mode).
* **Sichere Phasenumschaltung (1P/3P):** Führt bei aktiver Ladung eine automatisierte Stop-Wait-Switch-Start-Sequenz durch, um Hardwareschäden zu vermeiden.
* **Dynamisches Polling:** Polling-Intervall von 120s im Leerlauf (State A) und 15s während aktiver Sessions (State B/C).
* **On-Demand Refresh:** Sofortiges Feedback bei empfangenen Steuerbefehlen.
* **Erweitertes Home Assistant Auto-Discovery:** Automatische Registrierung aller Sensoren sowie interaktiver Steuerungselemente (Schalter, Schieberegler, Auswahlmenüs).

---

## Konfiguration (Home Assistant Add-on)

| Option | Beschreibung | Standardwert |
| :--- | :--- | :--- |
| `ALPHAESS_USERNAME` | Benutzername (E-Mail) für AlphaESS Cloud | *Erforderlich* |
| `ALPHAESS_PASSWORD` | Passwort für AlphaESS Cloud | *Erforderlich* |
| `ALPHAESS_BASE_URL` | Cloud Endpoint URL | `https://eurcloud.alphaess.com` |
| `MQTT_BROKER` | Adresse des MQTT Brokers | `mqtt://homeassistant:1883` |
| `MQTT_USER` | MQTT Benutzer (falls benötigt) | *optional* |
| `MQTT_PASSWORD` | MQTT Passwort (falls benötigt) | *optional* |
| `MQTT_BASE_TOPIC` | Basis-Topic für MQTT Status & Steuerung | `evcc/chargers/alphaess` |
| `MQTT_HA_DISCOVERY` | Home Assistant Auto-Discovery aktivieren | `true` |

---

## Home Assistant Integration (Auto-Discovery)

Wenn `MQTT_HA_DISCOVERY` aktiviert ist, wird die Wallbox automatisch als Gerät in Home Assistant angelegt und stellt folgende Entitäten bereit:

### Sensoren (Read-Only)
* **Wallbox Status** (`sensor`): Fahrzeugstatus (`A`, `B`, `C`, `F`)
* **Ladeleistung** (`sensor`): Berechnete Zielleistung in Watt (`W`)

### Steuerungselemente (Interactive Entities)
* **Ladefreigabe** (`switch`): Schalter zum Starten und Stoppen des Ladevorgangs.
* **Maximalstrom** (`number`): Schieberegler zur Wahl der Stromstärke (6 A bis 16 A).
* **Phasen** (`select`): Dropdown-Auswahl für 1-phasiges (`1`) oder 3-phasiges (`3`) Laden.
* **Lademodus** (`select`): Dropdown-Auswahl zwischen Custom/evcc (`4`) und Eco/Schonladung (`2`).

---

## MQTT Interface & evcc Integration

### Publish Topics (Status)

* `evcc/chargers/alphaess/status`: Vehicle Status (`A`, `B`, `C`, `F`)
* `evcc/chargers/alphaess/enabled`: Ladestatus (`true` / `false`)
* `evcc/chargers/alphaess/maxcurrent`: Aktuell eingestellte Stromstärke in Ampere
* `evcc/chargers/alphaess/power`: Errechnete Zielleistung in Watt
* `evcc/chargers/alphaess/phases`: Aktuell eingestellte Phasenzahl (`1` / `3`)

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