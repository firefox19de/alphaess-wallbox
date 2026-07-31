# AlphaESS Wallbox Control (Native Home Assistant Integration)

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/default)

Erweiterte Steuerungs-Integration für die **AlphaESS EVCT11 Wallbox** in Home Assistant via AlphaESS Web-API.

## Features

* **Direkte Web-API Anbindung:** Keine MQTT-Broker oder Node.js Middleware erforderlich.
* **Steuerung via HACS UI:** Bequeme Einrichtung direkt über den Config Flow.
* **Integrierter Hardware Guard Delay:** Automatische Sicherheits-Pausen bei der Phasenumschaltung (1P / 3P), um Relais und Schütze zu schonen.
* **Entitäten:**
  * `number.wallbox_maximalstrom`: Steuerung der Ladeleistung (6 A – 32 A).
  * `select.wallbox_lademodus`: Umschaltung zwischen Eco-Modi und Custom/evcc-Steuerung.
  * `select.wallbox_phasen`: Sichere Phasenwahl (1 Phase / 3 Phasen).

---

## Installation via HACS

1. In **HACS** oben rechts auf die 3 Punkte klicken -> **Benutzerdefinierte Repositories**.
2. URL hinzufügen: `https://github.com/firefox19de/alphaess-wallbox`
3. Kategorie: **Integration**.
4. Auf **Herunterladen** klicken und Home Assistant neu starten.
5. Unter **Einstellungen -> Geräte & Dienste -> Integration hinzufügen** nach `AlphaESS Wallbox Control` suchen.

---

## Disclaimer

Dieses Projekt ist eine inoffizielle Community-Integration. Es besteht keinerlei Verbindung zur Alpha ESS Co., Ltd. Die Nutzung erfolgt auf eigene Verantwortung.