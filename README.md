# AlphaESS Wallbox Control (Native Home Assistant Integration)

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/default)

Erweiterte Steuerungs-Integration für die **AlphaESS EVCT11 Wallbox** in Home Assistant via AlphaESS Web-API.

Diese Integration dient als **Ergänzung** zur offiziellen OpenAPI-Integration (z. B. von CharlesGillanders), um Parameter wie **Maximalstrom, Phasenumschaltung und Lademodus** zu steuern, die über die offizielle OpenAPI von AlphaESS nicht schreibbar sind.

---

## 💡 Das Hybrid-Konzept (OpenAPI + Web-API)

Um nicht in API Rate-Limits der Web-Cloud zu laufen und gleichzeitig maximale Stabilität bei Lade-Start/Stop zu garantieren, nutzt dieses Setup einen **Hybrid-Ansatz**:

1. **Lesen & Lade-Freigabe (OpenAPI):** Statuswerte, Ladeleistung sowie Start/Stop-Signale laufen über die offizielle AlphaESS-OpenAPI von CharlesGillanders.
2. **Parameter-Steuerung (Web-API):** Diese Custom Component übernimmt exklusiv das Schreiben von Phasenzahl, Ampere-Limit und Lademodus über die AlphaESS Web-API.

Damit bleiben die Funktionen klar getrennt: Die OpenAPI-Integration deckt die Lese- und Steuerungsfunktionen rund um den Ladeprozess ab, während diese Integration gezielt die Wallbox-Parameter schreibt, die in der offiziellen OpenAPI nicht verfügbar sind.

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

* **Direkte Web-API-Anbindung** zur AlphaESS-Cloud für Schreibzugriffe auf Wallbox-Parameter.
* **Setup via UI** über den Home Assistant Config Flow.
* **Entitäten für die Wallbox-Steuerung:**
  * `number.ev_charger_max_current_setting`: Steuerung der maximalen Stromstärke.
  * `select.ev_charger_phases`: Umschaltung zwischen 1-phasig und 3-phasig.
  * `select.ev_charger_charge_mode`: Auswahl des Lade- bzw. Betriebsmodus.
  * `button.ev_charger_refresh_status`: Aktualisierung des Status von der Cloud.

---

## ⚙️ Installation via HACS

1. In **HACS** oben rechts auf die 3 Punkte klicken -> **Benutzerdefinierte Repositories**.
2. URL hinzufügen: `https://github.com/firefox19de/alphaess-wallbox`
3. Kategorie: **Integration**.
4. Auf **Herunterladen** klicken und Home Assistant neu starten.
5. Unter **Einstellungen -> Geräte & Dienste -> Integration hinzufügen** nach `AlphaESS Wallbox Control` suchen.

---

## 🔧 Einrichtung in Home Assistant

Nach der Installation:

1. In Home Assistant zu **Einstellungen → Geräte & Dienste → Integration hinzufügen** gehen.
2. Nach **AlphaESS Wallbox Control** suchen und die Integration starten.
3. AlphaESS-Benutzername und Passwort eingeben.
4. Die Integration lädt anschließend die Wallbox-Daten aus der Cloud und erstellt die entsprechenden Entitäten.

> Die Integration nutzt die AlphaESS Web-API für Schreibzugriffe. Für reine Statusabfragen oder Start/Stop-Funktionalität kann sie ideal mit der offiziellen OpenAPI-Integration kombiniert werden.

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

### Praktisches Beispiel: EVCC-Bridge

Für Nutzer, die EVCC mit der Wallbox verbinden, kann die Bridge die MQTT-Topics für Ladezustand, Start/Stop, Stromstärke und Phasenumschaltung bereitstellen. Der hybride Ansatz sieht dabei so aus: Start und Stop laufen über die OpenAPI-Integration von CharlesGillanders, während Ampere und Phasenwahl über diese Web-API-Integration gesteuert werden.

```yaml
automation:
  - alias: "evcc Bridge: Command Receiver"
    id: evcc_bridge_command_receiver
    trigger:
      - platform: mqtt
        topic: ha_bridge/charger/enable/set
        id: charger_enable
      - platform: mqtt
        topic: ha_bridge/charger/maxcurrent/set
        id: charger_maxcurrent
      - platform: mqtt
        topic: ha_bridge/charger/phases/set
        id: charger_phases
    action:
      - choose:
          - conditions:
              - condition: template
                value_template: "{{ trigger.id == 'charger_enable' }}"
            sequence:
              - if:
                  - condition: template
                    value_template: "{{ trigger.payload == 'true' }}"
                  - condition: state
                    entity_id: binary_sensor.alb123456789012_can_start_charging
                    state: "on"
                then:
                  - action: button.press
                    target:
                      entity_id: button.alb123456789012_start_charging
                else:
                  - if:
                      - condition: template
                        value_template: "{{ trigger.payload == 'false' }}"
                      - condition: state
                        entity_id: binary_sensor.alb123456789012_can_stop_charging
                        state: "on"
                    then:
                      - action: button.press
                        target:
                          entity_id: button.alb123456789012_stop_charging

          - conditions:
              - condition: template
                value_template: "{{ trigger.id == 'charger_maxcurrent' }}"
            sequence:
              - action: number.set_value
                target:
                  entity_id: number.alpha_ess_charger_alp2468024680246_maximalstrom
                data:
                  value: "{{ trigger.payload | int }}"

          - conditions:
              - condition: template
                value_template: "{{ trigger.id == 'charger_phases' }}"
            sequence:
              - action: select.select_option
                target:
                  entity_id: select.alpha_ess_charger_alp2468024680246_phasen
                data:
                  option: "{{ trigger.payload }}-phasig"

  - alias: "evcc Bridge: Status Updates"
    id: evcc_bridge_status_updates
    trigger:
      - platform: homeassistant
        event: start
      - platform: state
        entity_id:
          - sensor.alb123456789012_ev_charger_status_raw
    action:
      - action: mqtt.publish
        data:
          topic: ha_bridge/charger/status
          retain: true
          payload: >
            {% set s = states('sensor.alb123456789012_ev_charger_status_raw') %}
            {% if s == '1' %} A {% elif s in ['2', '6'] %} B {% elif s in ['3', '4', '5'] %} C {% else %} F {% endif %}

      - action: mqtt.publish
        data:
          topic: ha_bridge/charger/enabled
          retain: true
          payload: >
            {% set s = states('sensor.alb123456789012_ev_charger_status_raw') %}
            {% if s in ['3', '4', '5'] %} true {% else %} false {% endif %}
```

Die Entity-Namen sollten im Beispiel durch die eigenen Namen im Home Assistant-System ersetzt werden. Der Kern ist der hybride Ablauf: Start/Stop über die OpenAPI-Integration, Ampere und Phasenwahl über diese Web-API-Integration.

---

## ⚠️ Hinweise und Einschränkungen

* Dieses Projekt ist eine inoffizielle Community-Integration.
* Es besteht keinerlei Verbindung zur Alpha ESS Co., Ltd.
* Die Nutzung erfolgt auf eigene Verantwortung.
* Die Funktionalität hängt von der Verfügbarkeit und dem Verhalten der AlphaESS-Web-API ab.

---

## 🤝 Beitrag

Beiträge sind willkommen. Wenn du Verbesserungen oder Fehlerberichte einreichen möchtest, ist ein Pull Request oder ein Issue gerne gesehen.
