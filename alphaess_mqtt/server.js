const fs = require('fs');
const axios = require('axios');
const CryptoJS = require('crypto-js');
const { wrapper } = require('axios-cookiejar-support');
const { CookieJar } = require('tough-cookie');
const mqtt = require('mqtt');
const pkg = require('./package.json');

const APP_NAME = 'AlphaESS MQTT Bridge';
const APP_VERSION = process.env.APP_VERSION || pkg.version || '0.0.0';

function log(level, message, ...extra) {
  const now = new Date();
  const pad = (n) => String(n).padStart(2, '0');
  const timestamp = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())} ${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`;
  console.log(`[${timestamp}] [${level}] ${message}`, ...extra);
}

const optionsPath = '/data/options.json';
if (fs.existsSync(optionsPath)) {
  log('CONFIG', 'Lese Optionen aus Home Assistant (/data/options.json)...');
  try {
    const rawOptions = fs.readFileSync(optionsPath, 'utf8');
    Object.assign(process.env, JSON.parse(rawOptions));
  } catch (err) {
    log('ERROR', 'Fehler beim Lesen von /data/options.json:', err.message);
  }
} else {
  require('dotenv').config();
}

log('INFO', '==============================================');
log('INFO', `--- ${APP_NAME} v${APP_VERSION} gestartet ---`);
log('INFO', '==============================================');

// --- CONFIGURATION & GUARDRAILS ---
const MIN_POLLING_SECONDS = Math.max(10, parseInt(process.env.MIN_POLLING_LIMIT, 10) || 10);

function getSanitizedInterval(userValue, defaultSeconds) {
  const val = parseInt(userValue, 10) || defaultSeconds;
  if (val < MIN_POLLING_SECONDS) {
    log('WARN', `Polling-Intervall von ${val}s unterschreitet Minimum. Setze Guardrail-Limit: ${MIN_POLLING_SECONDS}s.`);
    return MIN_POLLING_SECONDS;
  }
  return val;
}

const POLLING_IDLE_MS = getSanitizedInterval(process.env.POLLING_IDLE, 120) * 1000;
const POLLING_ACTIVE_MS = getSanitizedInterval(process.env.POLLING_ACTIVE, 15) * 1000;
const BACKOFF_DELAY_MS = (parseInt(process.env.BACKOFF_DELAY, 10) || 300) * 1000;

log('CONFIG', `Polling-Konfiguration: Idle=${POLLING_IDLE_MS / 1000}s | Active=${POLLING_ACTIVE_MS / 1000}s | Min-Limit=${MIN_POLLING_SECONDS}s | Backoff=${BACKOFF_DELAY_MS / 1000}s`);

const BASE_URL = process.env.ALPHAESS_BASE_URL || 'https://eurcloud.alphaess.com';
const USERNAME = process.env.ALPHAESS_USERNAME;
const PASSWORD = process.env.ALPHAESS_PASSWORD;
const AUTH_SCHEME = (process.env.ALPHAESS_AUTH_SCHEME || 'raw').toLowerCase();

const MQTT_BROKER = process.env.MQTT_BROKER || 'mqtt://homeassistant:1883';
const MQTT_USER = process.env.MQTT_USER;
const MQTT_PASSWORD = process.env.MQTT_PASSWORD;
const BASE_TOPIC = (process.env.MQTT_BASE_TOPIC || 'evcc/chargers/alphaess').replace(/\/+$/, '');
const HA_DISCOVERY = process.env.MQTT_HA_DISCOVERY !== 'false' && process.env.MQTT_HA_DISCOVERY !== false;
const HA_PREFIX = process.env.MQTT_HA_PREFIX || 'homeassistant';

const LOGIN_URL = 'login';
const API_PILOT_URL = '/api/usercenter/cloud/user/pilot';
const API_LOGIN_URL = '/api/usercenter/cloud/user/login';
const API_SYSTEM_URL = '/api/stable/home/getCustomMenuEssList';

const API_EV_GET_URL = '/api/iterate/newEv/getNewEvBySn';
const API_EV_STATUS_URL = '/api/iterate/ev/v2/getChargPileStatusByPileSn';
const API_EV_SET_URL = '/api/iterate/newEv/setNewEv';
const API_EV_START_URL = '/api/iterate/ev/startCharging';
const API_EV_STOP_URL = '/api/iterate/ev/stopCharging';

function calcTargetPowerKw(ampere, phase) {
  return Math.round(((Number(ampere || 0) * 230 * Number(phase || 3)) / 1000) * 100) / 100;
}

function encryptPassword(password, username) {
  const key = CryptoJS.SHA256(username);
  const iv = CryptoJS.MD5(username);
  return CryptoJS.AES.encrypt(password, key, {
    iv: iv,
    mode: CryptoJS.mode.CBC,
    padding: CryptoJS.pad.Pkcs7
  }).toString();
}

class AlphaESSClient {
  constructor() {
    this.accessToken = null;
    this.refreshToken = null;
    this.expiresAt = 0;
    this.systemSN = null;
    this.evChargerID = 'EV1';
    this.evChargerkey = null;
    this.evChargerSn = null;
    this.isLoggingIn = false;
    
    this.evStatusMap = new Map([
      [1, 'A'],
      [2, 'B'],
      [3, 'C'],
      [4, 'C'],
      [5, 'C'],
      [6, 'B'],
      [9, 'F']
    ]);

    this.evModeMap = new Map([
      [1, 'Eco / Langsamladung (Nur PV)'],
      [2, 'Eco / Schonladung (PV + Akku)'],
      [3, 'Eco / Schnellladung'],
      [4, 'Custom / Manuell (evcc-Steuerung)']
    ]);

    this.jar = new CookieJar();
    this.http = wrapper(axios.create({
      baseURL: BASE_URL,
      timeout: 30000,
      jar: this.jar,
      withCredentials: true,
      headers: {
        'Content-Type': 'application/json;charset=UTF-8',
        'Accept': 'application/json, text/plain, */*',
        'Origin': BASE_URL,
        'Referer': BASE_URL + '/',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
        'X-Requested-With': 'XMLHttpRequest',
        'Client-End': 'Web',
        'System': 'alphacloud',
        'platform': 'AK9D8H',
        'Language': 'de-DE'
      }
    }));

    this.http.interceptors.request.use((config) => {
      const now = new Date();
      const pad = (n) => String(n).padStart(2, '0');
      config.headers['operationDate'] = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())} ${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`;
      return config;
    });
  }

  authHeader() {
    const token = AUTH_SCHEME === 'bearer' ? `Bearer ${this.accessToken}` : this.accessToken;
    return { Authorization: token, token: this.accessToken };
  }

  async login() {
    if (this.isLoggingIn) return;
    this.isLoggingIn = true;
    try {
      if (!USERNAME || !PASSWORD) throw new Error('ALPHAESS_USERNAME oder ALPHAESS_PASSWORD fehlt');
      log('AUTH', 'Starte Login bei AlphaESS...');
      await this.http.post(LOGIN_URL);
      await this.http.post(API_PILOT_URL, { username: USERNAME, pilot: false });
      const res = await this.http.post(API_LOGIN_URL, {
        username: USERNAME,
        password: encryptPassword(PASSWORD, USERNAME)
      });
      const payload = res.data;
      if (!payload || !payload.data || !payload.data.token) {
        throw new Error(`Login fehlgeschlagen: code: ${payload ? payload.code : null}, msg: ${payload ? payload.msg : null}`);
      }
      this.accessToken = payload.data.token;
      this.refreshToken = payload.data.refreshToken || null;
      const expiresIn = Number(payload.data.expiresIn || 0);
      this.expiresAt = expiresIn > 0 ? Date.now() + (expiresIn - 60) * 1000 : Date.now() + 1800 * 1000;
      log('AUTH', 'Login bei AlphaESS erfolgreich!');
      return true;
    } finally {
      this.isLoggingIn = false;
    }
  }

  async ensureLogin() {
    if (!this.accessToken || Date.now() >= this.expiresAt) {
      await this.login();
    }
  }

  async getWithAuth(url) {
    await this.ensureLogin();
    try {
      const res = await this.http.get(url, { headers: this.authHeader() });
      if (res.data && (res.data.code === 401 || res.data.code === 403 || res.data.code === 4001)) {
        throw new Error('Token ungültig/abgelaufen');
      }
      return res.data;
    } catch (e) {
      if (e.response && (e.response.status === 429 || e.response.status === 403)) {
        throw e; // Durchreichen an Backoff-Handler
      }
      log('WARN', `Anfrage fehlgeschlagen (${e.message}). Erzwinge Erneuerung der Session...`);
      this.accessToken = null;
      await this.login();
      const res = await this.http.get(url, { headers: this.authHeader() });
      return res.data;
    }
  }

  async postWithAuth(url, body) {
    await this.ensureLogin();
    try {
      const res = await this.http.post(url, body, { headers: this.authHeader() });
      if (res.data && (res.data.code === 401 || res.data.code === 403 || res.data.code === 4001)) {
        throw new Error('Token ungültig/abgelaufen');
      }
      return res.data;
    } catch (e) {
      if (e.response && (e.response.status === 429 || e.response.status === 403)) {
        throw e; // Durchreichen an Backoff-Handler
      }
      log('WARN', `POST Anfrage fehlgeschlagen (${e.message}). Erzwinge Erneuerung der Session...`);
      this.accessToken = null;
      await this.login();
      const res = await this.http.post(url, body, { headers: this.authHeader() });
      return res.data;
    }
  }

  async loadSystemAndCharger() {
    if (this.systemSN && this.evChargerSn) return;
    
    log('INFO', 'Lade AlphaESS System-Daten...');
    const system = await this.getWithAuth(API_SYSTEM_URL);
    if (!system || !system.data || !system.data.length) throw new Error('Kein AlphaESS System gefunden');
    this.systemSN = system.data[0].sysSn;

    log('INFO', `System SN gefunden: ${this.systemSN}`);
    const ev = await this.getWithAuth(API_EV_GET_URL + '?sysSn=' + encodeURIComponent(this.systemSN));
    const oldPileData = ev && ev.data ? (ev.data.oldPileData || ev.data) : null;
    if (!oldPileData) throw new Error('Keine Wallbox-Daten gefunden');
    
    this.evChargerID = oldPileData.chargingpileId || 'EV1';
    this.evChargerkey = oldPileData.chargingpileKey;
    this.evChargerSn = oldPileData.chargingpileSn;
    log('INFO', `Wallbox SN: ${this.evChargerSn}`);
  }

  async getEvData() {
    await this.loadSystemAndCharger();
    const ev = await this.getWithAuth(API_EV_GET_URL + '?sysSn=' + encodeURIComponent(this.systemSN));
    if (!ev || !ev.data) throw new Error('Keine EV-Daten gefunden');
    return ev.data;
  }

  async status() {
    await this.loadSystemAndCharger();
    
    const statusUrl = API_EV_STATUS_URL + '?sysSn=' + encodeURIComponent(this.systemSN) + '&chargingpileId=' + encodeURIComponent(this.evChargerID);
    const status = await this.getWithAuth(statusUrl);
    
    const evData = await this.getEvData();
    const oldPileData = evData.oldPileData || evData;
    
    const mode = Number(status && status.data ? status.data.mode : 9);
    const chargingMode = Number(oldPileData.chargingmode || 4);
    const maxCurrent = Number(oldPileData.maxCurrent || 0);
    const phase = Number(oldPileData.chargingpilePhase || 3);

    const evccStatus = this.evStatusMap.get(mode) || 'A';
    const enabled = (evccStatus === 'C');
    const modeName = this.evModeMap.get(chargingMode) || `Unbekannt (${chargingMode})`;

    return {
      status_code: mode,
      evcc_status: evccStatus,
      ampere: maxCurrent,
      enabled: enabled,
      phase: phase,
      charging_mode: chargingMode,
      charging_mode_name: modeName,
      target_kw: calcTargetPowerKw(maxCurrent, phase),
      charger_sn: this.evChargerSn
    };
  }

  async setEnableState(enabled) {
    await this.loadSystemAndCharger();
    const url = enabled ? API_EV_START_URL : API_EV_STOP_URL;
    log('ALPHA', `[v${APP_VERSION}] Remote-Control Trigger via ${enabled ? 'startCharging' : 'stopCharging'} (Key: ${this.evChargerkey})`);
    return await this.postWithAuth(url, { id: this.evChargerkey });
  }

  async setAmpere(ampere, enabled = true, phase = null) {
    const evData = await this.getEvData();
    const oldPileData = evData.oldPileData || evData;
    const currentPhase = phase ? Number(phase) : Number(oldPileData.chargingpilePhase || 3);
    
    const newPileData = Object.assign({}, oldPileData, {
      chargingmode: oldPileData.chargingmode || 4,
      chargingpileSn: this.evChargerSn,
      chargingpileSwitch: true,
      chargingpilePhase: currentPhase,
      timeCharge1: false,
      timeChargeS1: '00:00',
      timeChargeE1: '23:59',
      timeCharge2: false,
      timeChargeS2: '00:00',
      timeChargeE2: '00:00',
      maxCurrent: Number(ampere)
    });
    const payload = {
      sysSn: this.systemSN,
      isNewPile: false,
      whetherToVerify: false,
      chargingpileControlOpen: true,
      currentsetting: evData.currentsetting || 32,
      oldPileData: newPileData
    };
    return await this.postWithAuth(API_EV_SET_URL, payload);
  }

  async setPhases(phases) {
    const currentStatus = await this.status();
    const wasCharging = currentStatus.enabled;
    const targetPhase = Number(phases) === 1 ? 1 : 3;
    
    log('ALPHA', `[v${APP_VERSION}] Phasenumschaltung auf ${targetPhase}P angefordert. (War aktiv: ${wasCharging})`);

    if (wasCharging) {
      log('ALPHA', `[v${APP_VERSION}] Pausiere Ladevorgang für Schützschaltung...`);
      await this.setEnableState(false);
      await new Promise((resolve) => setTimeout(resolve, 3500));
    }

    const evData = await this.getEvData();
    const oldPileData = evData.oldPileData || evData;
    
    const newPileData = Object.assign({}, oldPileData, {
      chargingpileSn: this.evChargerSn,
      chargingpileSwitch: true,
      chargingpilePhase: targetPhase
    });
    const payload = {
      sysSn: this.systemSN,
      isNewPile: false,
      whetherToVerify: false,
      chargingpileControlOpen: true,
      currentsetting: evData.currentsetting || 32,
      oldPileData: newPileData
    };
    
    log('ALPHA', `[v${APP_VERSION}] Sende Phasenkonfiguration an Cloud...`);
    const res = await this.postWithAuth(API_EV_SET_URL, payload);

    if (wasCharging) {
      log('ALPHA', `[v${APP_VERSION}] Phasenkonfiguration übermittelt. Warte auf Relais-Umschaltung (6s)...`);
      await new Promise((resolve) => setTimeout(resolve, 6000));
      log('ALPHA', `[v${APP_VERSION}] Re-aktiviere Ladevorgang via startCharging...`);
      await this.setEnableState(true);
    }

    return res;
  }

  async setMode(modeCode) {
    const evData = await this.getEvData();
    const oldPileData = evData.oldPileData || evData;
    
    log('ALPHA', `[v${APP_VERSION}] Setze Lademodus auf Code: ${modeCode}`);
    
    const newPileData = Object.assign({}, oldPileData, {
      chargingpileSn: this.evChargerSn,
      chargingpileSwitch: true,
      chargingmode: Number(modeCode)
    });
    const payload = {
      sysSn: this.systemSN,
      isNewPile: false,
      whetherToVerify: false,
      chargingpileControlOpen: true,
      currentsetting: evData.currentsetting || 32,
      oldPileData: newPileData
    };
    return await this.postWithAuth(API_EV_SET_URL, payload);
  }
}

const client = new AlphaESSClient();

let pollTimeoutTimer = null;
let haDiscoverySent = false;
let isBackoffActive = false;

async function executePoll() {
  let nextIntervalMs = POLLING_IDLE_MS;

  try {
    const data = await client.status();
    
    if (isBackoffActive) {
      log('POLL', '[API Recovery] Verbindung nach Rate-Limit/Sperre wiederhergestellt. Fahre mit normalem Polling fort.');
      isBackoffActive = false;
    }

    log('POLL', `Status: State ${data.evcc_status} | Phase: ${data.phase}P | Current: ${data.ampere}A | Enabled: ${data.enabled} | Mode: ${data.charging_mode_name}`);
    
    mqttClient.publish(`${BASE_TOPIC}/status`, data.evcc_status, { retain: true });
    mqttClient.publish(`${BASE_TOPIC}/enabled`, data.enabled ? 'true' : 'false', { retain: true });
    mqttClient.publish(`${BASE_TOPIC}/mode/code`, String(data.charging_mode), { retain: true });
    mqttClient.publish(`${BASE_TOPIC}/mode/state`, data.charging_mode_name, { retain: true });
    mqttClient.publish(`${BASE_TOPIC}/power`, String(data.target_kw * 1000), { retain: true });
    mqttClient.publish(`${BASE_TOPIC}/maxcurrent`, String(data.ampere), { retain: true });
    mqttClient.publish(`${BASE_TOPIC}/phases`, String(data.phase), { retain: true });

    if (HA_DISCOVERY && !haDiscoverySent && data.charger_sn) {
      publishHaDiscovery(data.charger_sn);
      haDiscoverySent = true;
    }

    // Dynamic Polling Interval Adjustment
    nextIntervalMs = (data.evcc_status === 'A') ? POLLING_IDLE_MS : POLLING_ACTIVE_MS;

  } catch (err) {
    const statusCode = err.response ? err.response.status : null;

    if (statusCode === 429 || statusCode === 403) {
      isBackoffActive = true;
      const jitterMs = Math.floor(Math.random() * 10000); // Jitter: 0 - 10s
      nextIntervalMs = BACKOFF_DELAY_MS + jitterMs;
      log('ERROR', `[Rate Limit / Auth Sperre HTTP ${statusCode}] Cloud-Limit erreicht! Pausiere Polling für ${Math.round(nextIntervalMs / 1000)}s...`);
    } else {
      log('ERROR', 'Fehler beim Statusabruf:', err.message);
      nextIntervalMs = POLLING_IDLE_MS;
    }
  } finally {
    scheduleNextPoll(nextIntervalMs);
  }
}

function scheduleNextPoll(delayMs) {
  if (pollTimeoutTimer) clearTimeout(pollTimeoutTimer);
  pollTimeoutTimer = setTimeout(executePoll, delayMs);
}

function publishHaDiscovery(chargerSn) {
  const deviceId = `alphaess_wallbox_${chargerSn.toLowerCase()}`;
  const device = {
    identifiers: [deviceId],
    name: "AlphaESS Wallbox",
    model: "EVCT11",
    manufacturer: "AlphaESS"
  };

  log('HA', `Sende erweiterte Home Assistant Auto-Discovery Pakete inkl. Steuerung (Prefix: ${HA_PREFIX})...`);

  mqttClient.publish(`${HA_PREFIX}/sensor/${deviceId}/status/config`, JSON.stringify({
    name: "Wallbox Status",
    unique_id: `${deviceId}_status`,
    state_topic: `${BASE_TOPIC}/status`,
    device: device,
    icon: "mdi:ev-station"
  }), { retain: true });

  mqttClient.publish(`${HA_PREFIX}/sensor/${deviceId}/power/config`, JSON.stringify({
    name: "Ladeleistung",
    unique_id: `${deviceId}_power`,
    state_topic: `${BASE_TOPIC}/power`,
    unit_of_measurement: "W",
    device_class: "power",
    device: device
  }), { retain: true });

  mqttClient.publish(`${HA_PREFIX}/switch/${deviceId}/enable/config`, JSON.stringify({
    name: "Ladefreigabe",
    unique_id: `${deviceId}_enable_switch`,
    state_topic: `${BASE_TOPIC}/enabled`,
    command_topic: `${BASE_TOPIC}/enable/set`,
    payload_on: "true",
    payload_off: "false",
    device: device,
    icon: "mdi:power"
  }), { retain: true });

  mqttClient.publish(`${HA_PREFIX}/number/${deviceId}/maxcurrent/config`, JSON.stringify({
    name: "Maximalstrom",
    unique_id: `${deviceId}_maxcurrent_number`,
    state_topic: `${BASE_TOPIC}/maxcurrent`,
    command_topic: `${BASE_TOPIC}/maxcurrent/set`,
    min: 6,
    max: 16,
    step: 1,
    unit_of_measurement: "A",
    mode: "slider",
    device: device,
    icon: "mdi:current-ac"
  }), { retain: true });

  mqttClient.publish(`${HA_PREFIX}/select/${deviceId}/phases/config`, JSON.stringify({
    name: "Phasen",
    unique_id: `${deviceId}_phases_select`,
    state_topic: `${BASE_TOPIC}/phases`,
    command_topic: `${BASE_TOPIC}/phases/set`,
    options: ["1", "3"],
    device: device,
    icon: "mdi:sine-wave"
  }), { retain: true });

  const modeOptions = Array.from(client.evModeMap.values());

  mqttClient.publish(`${HA_PREFIX}/select/${deviceId}/mode/config`, JSON.stringify({
    name: "Lademodus",
    unique_id: `${deviceId}_mode_select`,
    state_topic: `${BASE_TOPIC}/mode/state`,
    command_topic: `${BASE_TOPIC}/mode/set`,
    options: modeOptions,
    device: device,
    icon: "mdi:tune"
  }), { retain: true });
}

log('MQTT', `Verbinde mit Broker (${MQTT_BROKER})...`);
const mqttClient = mqtt.connect(MQTT_BROKER, {
  username: MQTT_USER,
  password: MQTT_PASSWORD,
  connectTimeout: 5000
});

mqttClient.on('connect', () => {
  log('MQTT', 'Erfolgreich mit Broker verbunden!');
  mqttClient.subscribe(`${BASE_TOPIC}/enable/set`);
  mqttClient.subscribe(`${BASE_TOPIC}/maxcurrent/set`);
  mqttClient.subscribe(`${BASE_TOPIC}/phases/set`);
  mqttClient.subscribe(`${BASE_TOPIC}/mode/set`);

  // Ersten Poll direkt ausführen (scheduleNextPoll übernimmt Folgetakt)
  executePoll();
});

mqttClient.on('error', (err) => {
  log('ERROR', 'MQTT Verbindungsfehler:', err.message);
});

mqttClient.on('message', async (topic, message) => {
  const payload = message.toString().trim();
  log('MQTT IN', `Topic: ${topic} -> Payload: ${payload}`);
  try {
    if (topic === `${BASE_TOPIC}/enable/set`) {
      const isEnable = payload === 'true';
      const res = await client.setEnableState(isEnable);
      log('ALPHA', `Enable/Disable-Ergebnis [v${APP_VERSION}]:`, JSON.stringify(res));
    } else if (topic === `${BASE_TOPIC}/maxcurrent/set`) {
      const current = Math.round(parseFloat(payload));
      const res = await client.setAmpere(current, true);
      log('ALPHA', `Stromstärken-Ergebnis [v${APP_VERSION}]:`, JSON.stringify(res));
    } else if (topic === `${BASE_TOPIC}/phases/set`) {
      const res = await client.setPhases(parseInt(payload, 10));
      log('ALPHA', `Phasen-Ergebnis [v${APP_VERSION}]:`, JSON.stringify(res));
    } else if (topic === `${BASE_TOPIC}/mode/set`) {
      let modeCode = 4; // Fallback: Custom

      for (const [code, name] of client.evModeMap.entries()) {
        if (name.toLowerCase() === payload.toLowerCase()) {
          modeCode = code;
          break;
        }
      }

      if (!isNaN(payload)) {
        modeCode = Number(payload);
      } else if (payload.toLowerCase() === 'custom') {
        modeCode = 4;
      } else if (payload.toLowerCase() === 'eco') {
        modeCode = 2;
      }

      const res = await client.setMode(modeCode);
      log('ALPHA', `Modus-Ergebnis [v${APP_VERSION}]:`, JSON.stringify(res));
    }

    // On-Demand Polling direkt nach dem Senden eines Befehls
    setTimeout(executePoll, 1500);
  } catch (err) {
    log('ERROR', 'Fehler bei Bearbeitung des MQTT-Befehls:', err.message);
  }
});