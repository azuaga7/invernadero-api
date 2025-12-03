from fastapi import FastAPI, UploadFile, File, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
from io import BytesIO
from pydantic import BaseModel
from typing import Optional, Dict, Any

app = FastAPI(title="Dashboard Invernadero ADTEC")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

LAST_DF = None

# Descripciones conocidas (ajusta según tus columnas reales)
KNOWN_FIELD_DESCRIPTIONS = {
    "timestamp": "Momento exacto en que se registró la medición (fecha y hora).",
    "dia_semana": "Día de la semana correspondiente al registro.",
    "modo_control": "Modo en que está trabajando el invernadero (automático o manual estacional).",
    "estacion": "Estación climática lógica que usa el controlador (verano/invierno).",
    "temp_invernadero_C": "Temperatura medida dentro del invernadero (sensor DS18B20).",
    "hum_invernadero_rel": "Humedad relativa (%) dentro del invernadero medida por el sensor de humedad.",
    "freq_ref_Hz": "Frecuencia objetivo calculada a partir de temperatura y estación.",
    "freq_cmd_Hz": "Frecuencia efectivamente enviada al variador de frecuencia.",
    "colg_ref_unidades": "Cantidad objetivo de ventiladores colgantes que el sistema desea activar.",
    "n_colg_vent_on": "Número real de ventiladores colgantes activados.",
    "relay_pared_on": "Estado del relé que alimenta los ventiladores de pared.",
    "relay_colg_1_on": "Estado del primer relé de ventiladores colgantes (banco 1).",
    "relay_colg_2_on": "Estado del segundo relé de ventiladores colgantes (banco 2).",
    "vent_pared_on": "Estado lógico global de ventiladores de pared.",
    "vent_colg_on": "Estado lógico global de ventiladores colgantes.",
    "vfd_freq_out_Hz": "Frecuencia de salida reportada por el variador de frecuencia.",
    "vfd_volt_out_V": "Tensión de salida aproximada del variador (V).",
    "vfd_curr_out_A": "Corriente de salida aproximada del variador (A).",
    "pump_on": "Estado actual de la bomba / nebulización (1 = encendida, 0 = apagada).",
    "pump_auto_mode": "Modo de la bomba: 1 = automático según condiciones, 0 = forzada por control remoto.",
}

def prettify_column_name(col: str) -> str:
    """Convierte nombres tipo 'temp_invernadero_C' en algo legible."""
    col2 = col.replace("_", " ").replace(".", " ").strip()
    if not col2:
        return col
    col2 = col2.lower()
    return col2[0].upper() + col2[1:]


DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <title>ADTEC · Dashboard Invernadero</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/xlsx@0.18.5/dist/xlsx.full.min.js"></script>
  <style>
    :root {
      --bg-color: #05070a;
      --card-color: #111827;
      --accent: #38bdf8;
      --accent-soft: rgba(56, 189, 248, 0.15);
      --text-main: #e5e7eb;
      --text-muted: #9ca3af;
      --success: #22c55e;
      --danger: #ef4444;
      --warn: #f59e0b;
      --cool: #0ea5e9;
      --adtec-yellow: #fbbf24;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: radial-gradient(circle at top, #020617 0, #020617 45%, #000 100%);
      color: var(--text-main);
    }
    .app-shell { min-height: 100vh; display: flex; flex-direction: column; }
    header {
      padding: 16px 32px;
      border-bottom: 1px solid rgba(148, 163, 184, 0.25);
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      backdrop-filter: blur(10px);
      background: linear-gradient(to right, rgba(15,23,42,0.95), rgba(15,23,42,0.4));
    }
    .logo { display: flex; align-items: center; gap: 12px; }
    .logo-icon {
      width: 36px; height: 36px; border-radius: 10px;
      background: linear-gradient(135deg, #0f172a, #020617);
      border: 1px solid rgba(248, 250, 252, 0.2);
      box-shadow: 0 0 25px rgba(250, 204, 21, 0.7);
      display: flex; align-items: center; justify-content: center;
      position: relative; overflow: hidden;
    }
    .logo-icon::before {
      content: ""; position: absolute; inset: -40%;
      background: conic-gradient(from 180deg, #22c55e, #0ea5e9, #fbbf24, #22c55e);
      opacity: 0.28; mix-blend-mode: screen;
    }
    .logo-icon-inner {
      position: relative; z-index: 1;
      font-size: 11px; font-weight: 700;
      color: var(--adtec-yellow); letter-spacing: 0.16em; text-transform: uppercase;
    }
    .logo-text-title {
      font-size: 17px; font-weight: 600;
      letter-spacing: 0.12em; text-transform: uppercase;
    }
    .logo-text-sub { font-size: 12px; color: var(--text-muted); }
    .logo-text-strong { font-weight: 700; color: var(--adtec-yellow); }
    main {
      flex: 1;
      padding: 12px 24px 32px;
      max-width: 1320px;
      margin: 0 auto;
      width: 100%;
    }
    .pill {
      font-size: 11px;
      padding: 4px 10px;
      border-radius: 999px;
      border: 1px solid rgba(148,163,184,0.5);
      color: var(--text-muted);
      display: inline-flex; align-items: center; gap: 4px;
    }
    .pill-dot {
      width: 7px; height: 7px; border-radius: 999px;
      background: var(--accent); box-shadow: 0 0 12px rgba(56,189,248,0.9);
    }
    .tabs {
      margin-top: 12px;
      display: flex; gap: 6px;
      border-bottom: 1px solid rgba(31,41,55,0.9);
      padding-bottom: 4px;
    }
    .tab {
      font-size: 12px; padding: 7px 14px;
      border-radius: 999px; border: 1px solid transparent;
      background: transparent; color: var(--text-muted);
      cursor: pointer; display: inline-flex; align-items: center; gap: 6px;
      transition: all 0.12s ease;
    }
    .tab-dot {
      width: 7px; height: 7px; border-radius: 999px;
      background: rgba(148,163,184,0.7);
    }
    .tab.active {
      border-color: rgba(56,189,248,0.7);
      background: radial-gradient(circle at top, rgba(56,189,248,0.22), rgba(15,23,42,0.98));
      color: var(--accent);
      box-shadow: 0 10px 28px rgba(15,23,42,0.9);
    }
    .tab.active .tab-dot {
      background: var(--accent);
      box-shadow: 0 0 12px rgba(56,189,248,0.9);
    }
    .tab-panel { display: none; margin-top: 14px; }
    .tab-panel.active { display: block; }
    .grid {
      display: grid;
      grid-template-columns: minmax(0, 3fr) minmax(0, 2fr);
      gap: 16px;
    }
    .card {
      background: linear-gradient(145deg, rgba(15,23,42,0.97), rgba(15,23,42,0.7));
      border-radius: 16px;
      padding: 16px 18px;
      border: 1px solid rgba(148, 163, 184, 0.35);
      box-shadow: 0 18px 45px rgba(15,23,42,0.9);
      position: relative; overflow: hidden;
    }
    .card-header {
      display: flex; justify-content: space-between; align-items: center;
      margin-bottom: 8px; position: relative; z-index: 1;
    }
    .card-title {
      font-size: 14px; letter-spacing: 0.08em;
      text-transform: uppercase; color: var(--text-muted);
    }
    .btn {
      border-radius: 999px;
      border: 1px solid rgba(56,189,248,0.7);
      background: radial-gradient(circle at top, rgba(56,189,248,0.2), rgba(15,23,42,0.95));
      color: var(--text-main);
      padding: 7px 14px; font-size: 12px;
      cursor: pointer; display: inline-flex; align-items: center; gap: 6px;
      transition: transform 0.12s ease, box-shadow 0.12s ease, background 0.12s ease;
    }
    .btn:hover {
      transform: translateY(-1px);
      box-shadow: 0 10px 28px rgba(56,189,248,0.45);
      background: radial-gradient(circle at top, rgba(56,189,248,0.3), rgba(15,23,42,1));
    }
    .btn-secondary {
      border-color: rgba(148,163,184,0.7);
      background: radial-gradient(circle at top, rgba(148,163,184,0.15), rgba(15,23,42,0.95));
      font-size: 11px; padding: 5px 10px;
    }
    .upload-area {
      border-radius: 14px;
      border: 1px dashed rgba(148, 163, 184, 0.8);
      padding: 16px 14px;
      display: flex; flex-direction: column; gap: 8px;
      background: radial-gradient(circle at top right, rgba(56,189,248,0.12), rgba(15,23,42,0.96));
    }
    .upload-row { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
    .form-label-inline { font-size: 11px; color: var(--text-muted); margin-right: 4px; }
    select, input[type="file"] {
      font-size: 12px; color: var(--text-main);
      background: rgba(15,23,42,0.9);
      border: 1px solid rgba(55,65,81,0.9);
      border-radius: 999px;
      padding: 6px 10px; outline: none;
    }
    select:focus {
      border-color: var(--accent);
      box-shadow: 0 0 0 1px rgba(56,189,248,0.5);
    }
    input[type="file"] { border-radius: 6px; }
    .controls-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 8px; margin-top: 10px;
    }
    .form-group { display: flex; flex-direction: column; gap: 3px; }
    .form-label {
      font-size: 11px; color: var(--text-muted);
      text-transform: uppercase; letter-spacing: 0.09em;
    }
    input[type="datetime-local"] {
      background: rgba(15,23,42,0.9);
      border-radius: 10px;
      border: 1px solid rgba(55,65,81,0.9);
      padding: 6px 8px; color: var(--text-main); font-size: 12px; outline: none; width: 100%;
    }
    .chip-toggle-group { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 6px; }
    .chip-toggle {
      font-size: 11px; padding: 4px 9px;
      border-radius: 999px; border: 1px solid rgba(148,163,184,0.7);
      background: rgba(15,23,42,0.85);
      color: var(--text-muted);
      cursor: pointer; display: inline-flex; align-items: center; gap: 4px;
    }
    .chip-toggle.active {
      border-color: var(--accent);
      background: var(--accent-soft);
      color: var(--accent);
    }
    .chip-toggle-dot {
      width: 6px; height: 6px; border-radius: 999px;
      background: rgba(148,163,184,0.9);
    }
    .chip-toggle.active .chip-toggle-dot {
      background: var(--accent);
      box-shadow: 0 0 10px rgba(56,189,248,0.8);
    }
    .chart-container {
      margin-top: 12px;
      padding: 8px;
      border-radius: 14px;
      background: radial-gradient(circle at top, rgba(15,23,42,0.5), rgba(2,6,23,0.98));
      border: 1px solid rgba(30,64,175,0.8);
      height: 360px;
    }
    #chartWideContainer { height: 460px; }
    canvas { width: 100% !important; height: 100% !important; }
    .status-grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px; margin-top: 8px;
    }
    .status-item {
      padding: 10px 12px;
      border-radius: 12px;
      background: radial-gradient(circle at top, rgba(15,118,110,0.3), rgba(15,23,42,0.96));
      border: 1px solid rgba(45,212,191,0.4);
      position: relative;
    }
    .status-item h3 {
      font-size: 11px;
      text-transform: uppercase; letter-spacing: 0.08em;
      color: var(--text-muted); margin: 0 0 4px;
    }
    .status-value { font-size: 16px; font-weight: 600; }
    .status-sub {
      font-size: 11px;
      color: var(--text-muted);
      margin-top: 2px;
    }
    .status-chip {
      display: inline-flex; align-items: center; gap: 6px;
      padding: 3px 8px; border-radius: 999px;
      font-size: 11px; margin-top: 4px;
      border: 1px solid rgba(148,163,184,0.4);
    }
    .status-chip.on {
      background: rgba(34,197,94,0.16);
      color: var(--success);
      border-color: rgba(34,197,94,0.6);
    }
    .status-dot {
      width: 8px; height: 8px; border-radius: 999px;
      background: rgba(148,163,184,0.9);
    }
    .status-dot.on {
      background: var(--success);
      box-shadow: 0 0 10px rgba(34,197,94,0.7);
    }
    .temp-bar {
      width: 100%;
      height: 8px;
      border-radius: 999px;
      background: linear-gradient(90deg, #0ea5e9, #22c55e, #f59e0b, #ef4444);
      margin-top: 6px;
      position: relative;
      overflow: hidden;
      opacity: 0.9;
    }
    .temp-bar-fill {
      position: absolute;
      top: 0;
      left: 0;
      height: 100%;
      border-radius: 999px;
      background: rgba(15,23,42,0.2);
      border-right: 2px solid rgba(249,250,251,0.9);
    }
    .temp-sparkline-wrapper {
      margin-top: 6px;
      height: 40px;
    }
    #tempSparkline {
      width: 100% !important;
      height: 100% !important;
    }
    .meta-info {
      font-size: 11px; color: var(--text-muted);
      margin-top: 6px;
      display: flex; justify-content: space-between;
      flex-wrap: wrap; gap: 4px;
    }
    .legend-dot {
      width: 10px; height: 10px; border-radius: 999px;
      border: 1px solid rgba(148,163,184,0.9);
    }
    .legend-dot.y1 {
      border-color: #38bdf8; box-shadow: 0 0 12px rgba(56,189,248,0.9);
    }
    .legend-dot.y2 {
      border-color: #a855f7; box-shadow: 0 0 12px rgba(168,85,247,0.9);
    }
    .empty-state {
      font-size: 13px; color: var(--text-muted);
      text-align: center; padding: 40px 16px;
    }
    .table-wrapper {
      margin-top: 8px;
      border-radius: 12px;
      border: 1px solid rgba(31,41,55,0.9);
      overflow: auto; max-height: 420px;
      background: rgba(15,23,42,0.98);
    }
    table { border-collapse: collapse; width: 100%; font-size: 12px; color: var(--text-main); }
    th, td {
      border-bottom: 1px solid rgba(31,41,55,0.9);
      padding: 6px 8px; text-align: left; white-space: nowrap;
    }
    th { position: sticky; top: 0; background: #020617; z-index: 1; }
    tr:nth-child(even) { background: rgba(15,23,42,0.9); }
    .fields-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px; margin-top: 8px;
    }
    .field-card {
      padding: 10px 12px;
      border-radius: 12px;
      background: radial-gradient(circle at top, rgba(30,64,175,0.3), rgba(15,23,42,0.96));
      border: 1px solid rgba(59,130,246,0.6);
      font-size: 12px;
    }
    .field-name { font-weight: 600; }
    .field-label { color: var(--accent); font-size: 11px; }
    .field-desc { margin-top: 4px; color: var(--text-muted); font-size: 11px; }
    @media (max-width: 960px) {
      .grid { grid-template-columns: minmax(0, 1fr); }
      header { flex-direction: column; align-items: flex-start; }
      .status-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .fields-grid { grid-template-columns: minmax(0, 1fr); }
    }
  </style>
</head>
<body>
  <div class="app-shell">
    <header>
      <div class="logo">
        <div class="logo-icon"><div class="logo-icon-inner">ADTEC</div></div>
        <div>
          <div class="logo-text-title">
            <span class="logo-text-strong">ADTEC Ingeniería</span> · Invernadero inteligente
          </div>
          <div class="logo-text-sub">Pozo canadiense · Control VFD · Telemetría local</div>
        </div>
      </div>
      <div class="pill">
        <div class="pill-dot"></div>
        <span id="datasetInfo">Sin archivo cargado</span>
      </div>
    </header>

    <main>
      <div class="tabs">
        <button class="tab active" data-tab="dashboard">
          <span class="tab-dot"></span>Dashboard
        </button>
        <button class="tab" data-tab="charts">
          <span class="tab-dot"></span>Gráficos
        </button>
        <button class="tab" data-tab="table">
          <span class="tab-dot"></span>Tabla de datos
        </button>
        <button class="tab" data-tab="control">
          <span class="tab-dot"></span>Control
        </button>
        <button class="tab" data-tab="fields">
          <span class="tab-dot"></span>Diccionario de campos
        </button>
      </div>

      <!-- TAB DASHBOARD -->
      <div class="tab-panel active" id="tab-dashboard">
        <div class="grid">
          <section class="card">
            <div class="card-header">
              <div class="card-title">Visualización general</div>
              <span style="font-size:11px;color:var(--text-muted);">
                La configuración de gráficos se realiza en la pestaña <strong>Gráficos</strong>.
              </span>
            </div>
            <div class="card-content">
              <div class="upload-area">
                <div class="upload-row">
                  <span class="form-label-inline">Modo de carga:</span>
                  <select id="uploadMode">
                    <option value="replace">Reemplazar datos</option>
                    <option value="append">Añadir a datos actuales</option>
                  </select>
                </div>
                <div class="upload-row">
                  <input type="file" id="fileInput" accept=".xlsx,.xls">
                  <button class="btn" id="btnUpload">⬆ Cargar datos</button>
                </div>
              </div>

              <div class="chart-container" id="chartContainer">
                <canvas id="chart"></canvas>
              </div>

              <div class="meta-info" id="chartMeta" style="display:none;">
                <span><span class="legend-dot y1"></span> Y1: <span id="metaY1"></span></span>
                <span><span class="legend-dot y2"></span> Y2: <span id="metaY2"></span></span>
                <span>Registros en la vista: <span id="metaCount"></span></span>
              </div>

              <div class="empty-state" id="emptyState">
                Sube un archivo Excel generado por tu sistema ESP32 para comenzar.<br>
                Luego entra en la pestaña <strong>Gráficos</strong> para elegir variables, fechas y filtros.
              </div>
            </div>
          </section>

          <section class="card">
            <div class="card-header">
              <div class="card-title">Estado actual del sistema</div>
            </div>
            <div class="card-content">
              <div class="status-grid">
                <div class="status-item" id="statusTempCard">
                  <h3>Clima interno</h3>
                  <div class="status-value" id="statusTemp">-- °C</div>
                  <div class="status-sub" id="statusTempRange">Mín: -- °C · Máx: -- °C</div>
                  <div class="temp-bar">
                    <div class="temp-bar-fill" id="tempBarFill" style="width:0%;"></div>
                  </div>
                  <div class="temp-sparkline-wrapper">
                    <canvas id="tempSparkline"></canvas>
                  </div>
                  <div class="status-chip" id="chipDayNight">
                    <span class="status-dot" id="dotDayNight"></span>
                    <span id="labelDayNight">Sin datos</span>
                  </div>
                </div>

                <div class="status-item">
                  <h3>Modo de trabajo</h3>
                  <div class="status-value" id="statusMode">--</div>
                  <div class="status-sub" id="statusModeDesc">Sin datos aún.</div>
                  <div class="status-chip" id="chipStation">
                    <span class="status-dot" id="dotStation"></span>
                    <span id="labelStation">Estación: --</span>
                  </div>
                </div>

                <div class="status-item">
                  <h3>Ventiladores pared</h3>
                  <div class="status-value" id="statusWall">--</div>
                  <div class="status-chip" id="chipWall">
                    <span class="status-dot" id="dotWall"></span>
                    <span id="labelWall">OFF</span>
                  </div>
                </div>
                <div class="status-item">
                  <h3>Ventiladores colgantes</h3>
                  <div class="status-value" id="statusColg">--</div>
                  <div class="status-sub" id="statusColgDetail">—</div>
                  <div class="status-chip" id="chipColg">
                    <span class="status-dot" id="dotColg"></span>
                    <span id="labelColg">OFF</span>
                  </div>
                </div>
              </div>

              <div class="status-grid" style="margin-top:12px;">
                <div class="status-item">
                  <h3>Frecuencia VFD</h3>
                  <div class="status-value" id="statusVfdFreq">-- Hz</div>
                </div>
                <div class="status-item">
                  <h3>Tensión VFD</h3>
                  <div class="status-value" id="statusVfdVolt">-- V</div>
                </div>
                <div class="status-item">
                  <h3>Consumo VFD</h3>
                  <div class="status-value" id="statusVfdCurr">-- A</div>
                </div>
                <div class="status-item">
                  <h3>Último registro</h3>
                  <div class="status-value" id="statusLastTs">--</div>
                </div>
              </div>

              <!-- NUEVOS WIDGETS -->
              <div class="status-grid" style="margin-top:12px;">
                <div class="status-item">
                  <h3>Estabilidad térmica (hoy)</h3>
                  <div class="status-value" id="statusTempStd">--</div>
                  <div class="status-sub" id="statusTempMean">Promedio: -- °C</div>
                </div>
                <div class="status-item">
                  <h3>Ventilación últimas 24 h</h3>
                  <div class="status-sub" id="statusVentHours">Pared: -- h · Colg.: -- h</div>
                  <div class="status-sub" id="statusVentSamples">Muestras analizadas: --</div>
                </div>
                <div class="status-item">
                  <h3>Energía estimada 24 h</h3>
                  <div class="status-value" id="statusEnergy">-- kWh</div>
                  <div class="status-sub" id="statusPowerMean">Potencia media: -- kW</div>
                </div>
                <div class="status-item">
                  <h3>Carga por modo (hoy)</h3>
                  <div class="status-sub" id="statusModeLoad">
                    Auto: -- h · Verano man.: -- h · Invierno man.: -- h
                  </div>
                </div>
              </div>
              <!-- FIN NUEVOS WIDGETS -->

            
                <div class="status-item" id="statusHumCard">
                  <h3>Humedad interna</h3>
                  <div class="status-value" id="statusHum">-- %</div>
                  <div class="status-sub" id="statusHumRange">Mín: -- % · Máx: -- %</div>
                  <div class="temp-bar">
                    <div class="temp-bar-fill" id="humBarFill" style="width:0%;"></div>
                  </div>
                </div>

                <div class="status-item">
                  <h3>Bomba / nebulización</h3>
                  <div class="status-value" id="statusPump">--</div>
                  <div class="status-chip" id="chipPump">
                    <span class="status-dot" id="dotPump"></span>
                    <span id="labelPump">OFF</span>
                  </div>
                </div>

                <div class="status-item">
                  <h3>Clima exterior</h3>
                  <div class="status-sub">Benjamín Aceval · Cerrito, Paraguay</div>
                  <div style="margin-top:8px;">
                    <a class="weatherwidget-io"
                       href="https://forecast7.com/en/n25d04n57d37/asuncion/"
                       data-label_1="BENJAMÍN ACEVAL"
                       data-label_2="CERRITO · PY"
                       data-theme="dark"
                       data-basecolor="#020617"
                       data-textcolor="#e5e7eb"
                       data-highcolor="#fbbf24"
                       data-lowcolor="#38bdf8"
                       data-suncolor="#fbbf24"
                       data-mooncolor="#38bdf8">
                      BENJAMÍN ACEVAL CERRITO · PY
                    </a>
                  </div>
                </div>
</div>
          </section>
        </div>
      </div>

      <!-- TAB GRAFICOS -->
      <div class="tab-panel" id="tab-charts">
        <section class="card">
          <div class="card-header">
            <div class="card-title">Laboratorio de gráficos</div>
            <button class="btn-secondary btn" id="btnReset">⟳ Reset filtros</button>
          </div>
          <div class="card-content">
            <p style="font-size:12px;color:var(--text-muted);margin:0 0 6px;">
              Aquí eliges qué variables graficar, en qué rango de fechas y si quieres ver sólo día o sólo noche.
              El gráfico grande de abajo se actualiza y el pequeño del Dashboard se mantiene sincronizado.
            </p>

            <div id="controlsWrapper" style="margin-top:10px; display:none;">
              <div class="controls-grid">
                <div class="form-group">
                  <label class="form-label">Variable eje Y principal</label>
                  <select id="selectY1"></select>
                </div>
                <div class="form-group">
                  <label class="form-label">Variable eje Y secundario</label>
                  <select id="selectY2">
                    <option value="">(sin eje secundario)</option>
                  </select>
                </div>
                <div class="form-group">
                  <label class="form-label">Columna de tiempo</label>
                  <select id="selectTime"></select>
                </div>
              </div>

              <div class="controls-grid" style="margin-top:8px;">
                <div class="form-group">
                  <label class="form-label">Desde</label>
                  <input type="datetime-local" id="fromDate">
                </div>
                <div class="form-group">
                  <label class="form-label">Hasta</label>
                  <input type="datetime-local" id="toDate">
                </div>
                <div class="form-group">
                  <label class="form-label">Vista</label>
                  <div class="chip-toggle-group">

                <div class="form-group">
                  <label class="form-label">Exportar</label>
                  <button class="btn" id="btnExportXlsx" type="button">⬇ Exportar XLSX</button>
                </div>
                    <button class="chip-toggle active" data-filter="all" id="fltAll">
                      <span class="chip-toggle-dot"></span>Todo el día
                    </button>
                    <button class="chip-toggle" data-filter="day" id="fltDay">
                      <span class="chip-toggle-dot"></span>Sólo horario diurno
                    </button>
                    <button class="chip-toggle" data-filter="night" id="fltNight">
                      <span class="chip-toggle-dot"></span>Sólo horario nocturno
                    </button>
                  </div>
                </div>
              </div>
            </div>

            <div class="chart-container" id="chartWideContainer">
              <canvas id="chartWide"></canvas>
            </div>
          </div>
        </section>
      </div>

      <!-- TAB TABLA -->
      <div class="tab-panel" id="tab-table">
        <section class="card">
          <div class="card-header">
            <div class="card-title">Tabla de registros</div>
          </div>
          <div class="card-content">
            <p style="font-size:12px;color:var(--text-muted);margin:0 0 6px;">
              Visualización tabular de los datos capturados (muestra hasta 300 filas para no saturar el navegador).
            </p>
            <div class="table-wrapper" id="tableWrapper"></div>
          </div>
        </section>
      </div>

      
      <!-- TAB CONTROL -->
      <div class="tab-panel" id="tab-control">
        <section class="card">
          <div class="card-header">
            <div class="card-title">Control remoto de equipos</div>
          </div>
          <div class="card-content">
            <p style="font-size:12px;color:var(--text-muted);margin:0 0 6px;">
              Desde aquí puedes ver el estado actual reportado por el ESP32 y enviar órdenes manuales
              a los relés de pared, colgantes y bomba / nebulización.
            </p>

            <div class="controls-grid" style="margin-top:10px;">
              <div class="form-group">
                <label class="form-label">Ventiladores pared</label>
                <div class="status-sub" id="ctrlWallState">Estado actual: --</div>
                <div class="chip-toggle-group" style="margin-top:6px;">
                  <label class="status-sub">
                    <input type="checkbox" id="ctrlWallManual"> Modo manual
                  </label>
                  <label class="status-sub">
                    <input type="checkbox" id="ctrlWallOn"> Forzar ON
                  </label>
                </div>
              </div>

              <div class="form-group">
                <label class="form-label">Ventiladores colgantes</label>
                <div class="status-sub" id="ctrlColgState">Estado actual: --</div>
                <div class="status-sub" id="ctrlColgDetail">Cantidad objetivo / real: --</div>
                <div class="chip-toggle-group" style="margin-top:6px;">
                  <label class="status-sub">
                    <input type="checkbox" id="ctrlColgManual"> Modo manual
                  </label>
                  <label class="status-sub">
                    <input type="checkbox" id="ctrlColgOn"> Forzar ON
                  </label>
                </div>
              </div>

              <div class="form-group">
                <label class="form-label">Bomba / nebulización</label>
                <div class="status-sub" id="ctrlPumpState">Estado actual: --</div>
                <div class="chip-toggle-group" style="margin-top:6px;">
                  <label class="status-sub">
                    <input type="checkbox" id="ctrlPumpManual"> Modo manual
                  </label>
                  <label class="status-sub">
                    <input type="checkbox" id="ctrlPumpOn"> Forzar ON
                  </label>
                </div>
              </div>
            </div>

            <div style="margin-top:12px; display:flex; gap:8px; flex-wrap:wrap;">
              <button class="btn" id="btnApplyControl">Aplicar cambios</button>
              <span style="font-size:11px;color:var(--text-muted);" id="ctrlStatusMsg">
                Los cambios se envían a /api/control_state y serán leídos por el ESP32 en su próximo ciclo.
              </span>
            </div>
          </div>
        </section>
      </div>

<!-- TAB CAMPOS -->
      <div class="tab-panel" id="tab-fields">
        <section class="card">
          <div class="card-header">
            <div class="card-title">Diccionario de campos</div>
          </div>
          <div class="card-content">
            <p style="font-size:12px;color:var(--text-muted);margin:0 0 6px;">
              Aquí ves el nombre real de cada columna (como está en el Excel),
              la etiqueta legible que usa la interfaz y una descripción funcional.
            </p>
            <div class="fields-grid" id="fieldsGrid"></div>
          </div>
        </section>
      </div>
    </main>
  </div>

  
  <script>
    (function() {
      var d = document;
      var id = "weatherwidget-io-js";
      if (!d.getElementById(id)) {
        var s = d.createElement("script");
        s.id = id;
        s.src = "https://weatherwidget.io/js/widget.min.js";
        s.async = true;
        d.head.appendChild(s);
      }
    })();
  </script>

<script>
    let globalData = null;
    let globalChart = null;
    let globalChartWide = null;
    let currentFilter = "all";

    function setDatasetInfo(text) {
      document.getElementById("datasetInfo").textContent = text;
    }

    function setEmptyState(visible) {
      document.getElementById("emptyState").style.display = visible ? "block" : "none";
      document.getElementById("controlsWrapper").style.display = visible ? "none" : "block";
      document.getElementById("chartMeta").style.display = visible ? "none" : "flex";
    }

    function accentChip(el, on) {
      if (!el) return;
      if (on) el.classList.add("active"); else el.classList.remove("active");
    }

    function applyFilterButtons() {
      accentChip(document.getElementById("fltAll"), currentFilter === "all");
      accentChip(document.getElementById("fltDay"), currentFilter === "day");
      accentChip(document.getElementById("fltNight"), currentFilter === "night");
    }

    async function uploadFile() {
      const input = document.getElementById("fileInput");
      const mode = document.getElementById("uploadMode").value || "replace";
      if (!input.files || !input.files.length) {
        alert("Selecciona un archivo Excel primero.");
        return;
      }
      const formData = new FormData();
      formData.append("file", input.files[0]);
      setDatasetInfo("Subiendo archivo...");
      try {
        const resp = await fetch("/upload?mode=" + encodeURIComponent(mode), {
          method: "POST",
          body: formData
        });
        if (!resp.ok) {
          const txt = await resp.text();
          alert("Error al subir el archivo: " + txt);
          setDatasetInfo("Error en subida");
          return;
        }
        const json = await resp.json();
        setDatasetInfo(`Archivo: ${json.filename} · ${json.rows} filas, ${json.columns.length} columnas`);
        await loadData();
      } catch (err) {
        console.error(err);
        alert("Error de red al subir el archivo.");
        setDatasetInfo("Error de red");
      }
    }

    async function loadData() {
      try {
        const resp = await fetch("/api/data");
        if (!resp.ok) {
          setEmptyState(true);
          return;
        }
        globalData = await resp.json();
        if (!globalData.rows || !globalData.rows.length) {
          setEmptyState(true);
          return;
        }
        initControls();
        updateStatusFromData();
        updateChart();
        renderTable();
        renderFieldsDictionary();
        setEmptyState(false);
      } catch (err) {
        console.error(err);
        setEmptyState(true);
      }
    }

    function findPreferredColumn(candidates, inList) {
      for (const c of candidates) {
        if (inList.includes(c)) return c;
      }
      return inList[0] || null;
    }

    function initControls() {
      if (!globalData) return;
      const numericCols = globalData.numericColumns || [];
      const timeCols = globalData.datetimeColumns || [];
      const labels = globalData.fieldFriendlyLabels || {};

      const selectY1 = document.getElementById("selectY1");
      const selectY2 = document.getElementById("selectY2");
      const selectTime = document.getElementById("selectTime");

      if (!selectY1 || !selectY2 || !selectTime) return;

      selectY1.innerHTML = "";
      selectY2.innerHTML = '<option value="">(sin eje secundario)</option>';
      selectTime.innerHTML = "";

      numericCols.forEach(col => {
        const label = labels[col] || col;
        const opt1 = document.createElement("option");
        opt1.value = col;
        opt1.textContent = label;
        selectY1.appendChild(opt1);

        const opt2 = document.createElement("option");
        opt2.value = col;
        opt2.textContent = label;
        selectY2.appendChild(opt2);
      });

      timeCols.forEach(col => {
        const label = labels[col] || col;
        const opt = document.createElement("option");
        opt.value = col;
        opt.textContent = label;
        selectTime.appendChild(opt);
      });

      const preferredY1 = findPreferredColumn(
        ["temp_invernadero_C", "tempC", "temperatura"],
        numericCols
      );
      const preferredY2 = findPreferredColumn(
        ["vfd_freq_out_Hz", "freq_cmd_Hz", "freq_ref_Hz"],
        numericCols
      );
      const preferredTime = findPreferredColumn(
        ["timestamp", "FechaHora", "fecha_hora"],
        timeCols
      );

      if (preferredY1) selectY1.value = preferredY1;
      if (preferredY2) selectY2.value = preferredY2;
      if (preferredTime) selectTime.value = preferredTime;

      document.getElementById("fromDate").value = "";
      document.getElementById("toDate").value = "";
    }

    function parseDateFromRow(row, timeCol) {
      if (!timeCol || !row[timeCol]) return null;
      const d = new Date(row[timeCol]);
      if (isNaN(d.getTime())) return null;
      return d;
    }

    function filterRows() {
      if (!globalData) return [];
      const rows = globalData.rows || [];
      const timeCol = document.getElementById("selectTime").value;

      const fromStr = document.getElementById("fromDate").value;
      const toStr = document.getElementById("toDate").value;
      const fromDate = fromStr ? new Date(fromStr) : null;
      const toDate = toStr ? new Date(toStr) : null;

      return rows.filter(row => {
        const d = parseDateFromRow(row, timeCol);
        if (d) {
          if (fromDate && d < fromDate) return false;
          if (toDate && d > toDate) return false;
        }
        if (currentFilter === "day" || currentFilter === "night") {
          if (!d) return false;
          const hour = d.getHours();
          const isDay = hour >= 7 && hour < 19;
          if (currentFilter === "day" && !isDay) return false;
          if (currentFilter === "night" && isDay) return false;
        }
        return true;
      });
    }

    
    function exportXlsx() {
      if (!globalData || !globalData.rows || !globalData.rows.length) {
        alert("No hay datos para exportar.");
        return;
      }
      if (typeof XLSX === "undefined") {
        alert("La librería XLSX no está disponible en esta página.");
        return;
      }
      const rows = filterRows();
      if (!rows.length) {
        alert("No hay filas en el rango seleccionado.");
        return;
      }
      const cols = globalData.columns || [];
      const dataForSheet = rows.map(r => {
        const obj = {};
        cols.forEach(c => {
          obj[c] = r[c];
        });
        return obj;
      });
      const wb = XLSX.utils.book_new();
      const ws = XLSX.utils.json_to_sheet(dataForSheet);
      XLSX.utils.book_append_sheet(wb, ws, "datos_filtrados");
      XLSX.writeFile(wb, "invernadero_export.xlsx");
    }

    function buildDatasetsAndLabels() {
      if (!globalData) return { labels: [], datasets: [] };

      const y1 = document.getElementById("selectY1")?.value;
      const y2 = document.getElementById("selectY2")?.value;
      const timeCol = document.getElementById("selectTime")?.value;
      const labelsDict = globalData.fieldFriendlyLabels || {};

      const filtered = filterRows();
      const labels = [];
      const dataY1 = [];
      const dataY2 = [];

      filtered.forEach(row => {
        const d = parseDateFromRow(row, timeCol);
        labels.push(d ? d : row[timeCol] || "");
        dataY1.push(y1 ? Number(row[y1]) : null);
        if (y2) dataY2.push(Number(row[y2]));
      });

      const datasets = [];
      if (y1) {
        datasets.push({
          label: labelsDict[y1] || y1,
          data: dataY1,
          borderColor: "rgba(56,189,248,0.9)",
          backgroundColor: "rgba(56,189,248,0.2)",
          borderWidth: 2,
          tension: 0.25,
          yAxisID: "y1",
          pointRadius: 0
        });
      }
      if (y2) {
        datasets.push({
          label: labelsDict[y2] || y2,
          data: dataY2,
          borderColor: "rgba(168,85,247,0.9)",
          backgroundColor: "rgba(168,85,247,0.18)",
          borderWidth: 2,
          tension: 0.25,
          yAxisID: "y2",
          pointRadius: 0
        });
      }

      return { labels, datasets, filtered, labelsDict, y1, y2 };
    }

    function updateChart() {
      if (!globalData) return;

      const ctxMain = document.getElementById("chart").getContext("2d");
      const ctxWide = document.getElementById("chartWide").getContext("2d");

      const { labels, datasets, filtered, labelsDict, y1, y2 } = buildDatasetsAndLabels();

      const baseOptions = {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        scales: {
          x: {
            ticks: { color: "rgba(148,163,184,0.9)", maxRotation: 0, autoSkip: true },
            grid: { color: "rgba(31,41,55,0.8)" }
          },
          y1: {
            position: "left",
            ticks: { color: "rgba(56,189,248,0.9)" },
            grid: { color: "rgba(31,41,55,0.7)" }
          },
          y2: {
            position: "right",
            ticks: { color: "rgba(168,85,247,0.9)" },
            grid: { drawOnChartArea: false }
          }
        },
        plugins: {
          legend: {
            labels: { color: "rgba(209,213,219,0.9)" }
          }
        }
      };

      if (globalChart) globalChart.destroy();
      globalChart = new Chart(ctxMain, {
        type: "line",
        data: { labels, datasets },
        options: baseOptions
      });

      if (globalChartWide) globalChartWide.destroy();
      globalChartWide = new Chart(ctxWide, {
        type: "line",
        data: { labels, datasets },
        options: baseOptions
      });

      document.getElementById("metaY1").textContent = y1 ? (labelsDict[y1] || y1) : "—";
      document.getElementById("metaY2").textContent = y2 ? (labelsDict[y2] || y2) : "—";
      document.getElementById("metaCount").textContent = filtered.length;
    }

    function setOnOffChip(chipId, dotId, labelId, isOn, textIfOn, textIfOff) {
      const chip = document.getElementById(chipId);
      const dot = document.getElementById(dotId);
      const label = document.getElementById(labelId);
      if (!chip || !dot || !label) return;
      if (isOn) {
        chip.classList.add("on");
        dot.classList.add("on");
        label.textContent = textIfOn || "ON";
      } else {
        chip.classList.remove("on");
        dot.classList.remove("on");
        label.textContent = textIfOff || "OFF";
      }
    }

    function tempColorForValue(t) {
      if (t === null || isNaN(t)) return "#6b7280";
      if (t < 18) return "#0ea5e9";
      if (t < 26) return "#22c55e";
      if (t < 32) return "#f59e0b";
      return "#ef4444";
    }

    function drawTempSparkline(dayTemps) {
      const canvas = document.getElementById("tempSparkline");
      if (!canvas) return;
      const ctx = canvas.getContext("2d");
      const w = canvas.width = canvas.clientWidth;
      const h = canvas.height = canvas.clientHeight;

      ctx.clearRect(0, 0, w, h);

      if (!dayTemps || !dayTemps.length) return;
      const minT = Math.min(...dayTemps);
      const maxT = Math.max(...dayTemps);
      const color = tempColorForValue(dayTemps[dayTemps.length - 1]);

      ctx.beginPath();
      dayTemps.forEach((t, idx) => {
        const x = (idx / (dayTemps.length - 1 || 1)) * (w - 4) + 2;
        let y = h / 2;
        if (maxT > minT) {
          const norm = (t - minT) / (maxT - minT);
          y = (1 - norm) * (h - 6) + 3;
        }
        if (idx === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.strokeStyle = color;
      ctx.lineWidth = 1.5;
      ctx.stroke();
    }

    function computeStd(values) {
      if (!values || values.length === 0) return null;
      const mean = values.reduce((a, b) => a + b, 0) / values.length;
      const variance = values.reduce((acc, v) => acc + Math.pow(v - mean, 2), 0) / values.length;
      return Math.sqrt(variance);
    }

    function updateTemperatureVisuals() {
      if (!globalData || !globalData.rows || !globalData.rows.length) return;
      const rows = globalData.rows;
      const cols = globalData.columns || [];
      const timeCols = globalData.datetimeColumns || [];

      const timeCol = timeCols.includes("timestamp")
        ? "timestamp"
        : (timeCols[0] || null);

      const tempCol = cols.find(c => ["temp_invernadero_C", "tempC", "temperatura"].includes(c));
      if (!tempCol) return;

      let lastRow = rows[rows.length - 1];
      if (timeCol) {
        const sorted = [...rows].filter(r => r[timeCol]).sort((a, b) => {
          return new Date(a[timeCol]) - new Date(b[timeCol]);
        });
        if (sorted.length) lastRow = sorted[sorted.length - 1];
      }

      const lastTemp = lastRow[tempCol] !== undefined ? Number(lastRow[tempCol]) : null;

      let refDate = null;
      if (timeCol && lastRow[timeCol]) {
        const d = new Date(lastRow[timeCol]);
        if (!isNaN(d.getTime())) refDate = d;
      }

      let dayTemps = [];
      if (refDate && timeCol) {
        const day = refDate.getDate();
        const month = refDate.getMonth();
        const year = refDate.getFullYear();
        rows.forEach(r => {
          if (!r[timeCol]) return;
          const d = new Date(r[timeCol]);
          if (isNaN(d.getTime())) return;
          if (d.getDate() === day && d.getMonth() === month && d.getFullYear() === year) {
            const tv = Number(r[tempCol]);
            if (!isNaN(tv)) dayTemps.push(tv);
          }
        });
      }

      if (!dayTemps.length) {
        dayTemps = rows
          .map(r => Number(r[tempCol]))
          .filter(v => !isNaN(v));
      }

      let minT = null;
      let maxT = null;
      let meanT = null;
      let stdT = null;
      if (dayTemps.length) {
        minT = Math.min(...dayTemps);
        maxT = Math.max(...dayTemps);
        meanT = dayTemps.reduce((a, b) => a + b, 0) / dayTemps.length;
        stdT = computeStd(dayTemps);
      }

      const rangeLabel = document.getElementById("statusTempRange");
      if (rangeLabel) {
        if (minT !== null && maxT !== null) {
          rangeLabel.textContent = `Mín: ${minT.toFixed(1)} °C · Máx: ${maxT.toFixed(1)} °C`;
        } else {
          rangeLabel.textContent = "Mín: -- °C · Máx: -- °C";
        }
      }

      const tempValueLabel = document.getElementById("statusTemp");
      if (tempValueLabel) {
        tempValueLabel.textContent =
          (lastTemp !== null && !isNaN(lastTemp)) ? `${lastTemp.toFixed(1)} °C` : "-- °C";
      }

      const barFill = document.getElementById("tempBarFill");
      if (barFill) {
        let pct = 50;
        if (minT !== null && maxT !== null && maxT > minT && lastTemp !== null && !isNaN(lastTemp)) {
          pct = ((lastTemp - minT) / (maxT - minT)) * 100;
          if (pct < 0) pct = 0;
          if (pct > 100) pct = 100;
        }
        barFill.style.width = pct + "%";
        barFill.style.backgroundColor = tempColorForValue(lastTemp);
      }

      const tempCard = document.getElementById("statusTempCard");
      if (tempCard) {
        const color = tempColorForValue(lastTemp);
        tempCard.style.boxShadow = `0 0 24px ${color}40`;
        tempCard.style.borderColor = `${color}80`;
      }

      const stdLabel = document.getElementById("statusTempStd");
      const meanLabel = document.getElementById("statusTempMean");
      if (stdLabel) {
        if (stdT !== null) {
          stdLabel.textContent = stdT.toFixed(2) + " °C";
        } else {
          stdLabel.textContent = "--";
        }
      }
      if (meanLabel) {
        if (meanT !== null) {
          meanLabel.textContent = `Promedio: ${meanT.toFixed(1)} °C`;
        } else {
          meanLabel.textContent = "Promedio: -- °C";
        }
      }

      drawTempSparkline(dayTemps);
    }

    function estimateStepHours(rows, timeCol) {
      if (!timeCol) return 0.5;
      const times = [];
      rows.forEach(r => {
        if (!r[timeCol]) return;
        const d = new Date(r[timeCol]);
        if (!isNaN(d.getTime())) times.push(d.getTime());
      });
      if (times.length < 2) return 0.5;
      times.sort((a, b) => a - b);
      let diffs = [];
      for (let i = 1; i < times.length; i++) {
        diffs.push(times[i] - times[i - 1]);
      }
      if (!diffs.length) return 0.5;
      const avgMs = diffs.reduce((a, b) => a + b, 0) / diffs.length;
      let hours = avgMs / (1000 * 60 * 60);
      if (hours < 0.05) hours = 0.05;
      if (hours > 1.5) hours = 1.5;
      return hours;
    }

    function updateSummaryWidgets() {
      if (!globalData || !globalData.rows || !globalData.rows.length) return;
      const rows = globalData.rows;
      const cols = globalData.columns || [];
      const timeCols = globalData.datetimeColumns || [];

      const timeCol = timeCols.includes("timestamp")
        ? "timestamp"
        : (timeCols[0] || null);

      if (!timeCol) {
        document.getElementById("statusVentHours").textContent = "Pared: -- h · Colg.: -- h";
        document.getElementById("statusVentSamples").textContent = "Muestras analizadas: --";
        document.getElementById("statusEnergy").textContent = "-- kWh";
        document.getElementById("statusPowerMean").textContent = "Potencia media: -- kW";
        document.getElementById("statusModeLoad").textContent = "Auto: -- h · Verano man.: -- h · Invierno man.: -- h";
        return;
      }

      let sorted = rows.filter(r => r[timeCol]).slice();
      sorted.sort((a, b) => new Date(a[timeCol]) - new Date(b[timeCol]));
      if (!sorted.length) return;

      const lastDate = new Date(sorted[sorted.length - 1][timeCol]);
      if (isNaN(lastDate.getTime())) return;

      const cutoff24 = new Date(lastDate.getTime() - 24 * 60 * 60 * 1000);

      const rows24 = sorted.filter(r => {
        const d = new Date(r[timeCol]);
        if (isNaN(d.getTime())) return false;
        return d >= cutoff24 && d <= lastDate;
      });

      const stepHours = estimateStepHours(sorted, timeCol);

      const wallCol = cols.find(c => ["vent_pared_on", "relay_pared_on", "wallFansOn"].includes(c));
      const colgCol = cols.find(c => ["vent_colg_on", "n_colg_vent_on", "colgFansOn"].includes(c));

      let wallOnCount = 0;
      let colgOnCount = 0;

      rows24.forEach(r => {
        if (wallCol) {
          const v = Number(r[wallCol]);
          if (!isNaN(v) && v > 0) wallOnCount++;
        }
        if (colgCol) {
          const v = Number(r[colgCol]);
          if (!isNaN(v) && v > 0) colgOnCount++;
        }
      });

      const hoursWall = wallOnCount * stepHours;
      const hoursColg = colgOnCount * stepHours;

      const ventHoursLabel = document.getElementById("statusVentHours");
      const ventSamplesLabel = document.getElementById("statusVentSamples");
      if (ventHoursLabel) {
        ventHoursLabel.textContent = `Pared: ${hoursWall.toFixed(1)} h · Colg.: ${hoursColg.toFixed(1)} h`;
      }
      if (ventSamplesLabel) {
        ventSamplesLabel.textContent = `Muestras analizadas: ${rows24.length}`;
      }

      const voltCol = cols.find(c => ["vfd_volt_out_V"].includes(c));
      const currCol = cols.find(c => ["vfd_curr_out_A"].includes(c));
      const freqCol = cols.find(c => ["vfd_freq_out_Hz", "freq_cmd_Hz"].includes(c));
      let energyKWh = 0;
      let powerSamples = 0;
      let sumPower = 0;

      rows24.forEach(r => {
        if (!voltCol || !currCol) return;
        const v = Number(r[voltCol]);
        const i = Number(r[currCol]);
        if (isNaN(v) || isNaN(i) || v <= 0 || i <= 0) return;
        let freqOk = true;
        if (freqCol) {
          const f = Number(r[freqCol]);
          if (isNaN(f) || f <= 0.5) freqOk = false;
        }
        if (!freqOk) return;
        const p_kw = v * i * 0.001 * 0.9;
        energyKWh += p_kw * stepHours;
        sumPower += p_kw;
        powerSamples++;
      });

      const powerMean = powerSamples > 0 ? (sumPower / powerSamples) : null;

      const energyLabel = document.getElementById("statusEnergy");
      const powerLabel = document.getElementById("statusPowerMean");
      if (energyLabel) {
        energyLabel.textContent = energyKWh > 0 ? energyKWh.toFixed(2) + " kWh" : "-- kWh";
      }
      if (powerLabel) {
        powerLabel.textContent = powerMean !== null ? "Potencia media: " + powerMean.toFixed(2) + " kW" : "Potencia media: -- kW";
      }

      const modeCol = cols.find(c => ["modo_control", "modo", "controlMode"].includes(c));
      const modeLoadLabel = document.getElementById("statusModeLoad");

      if (modeCol && modeLoadLabel) {
        let autoCount = 0;
        let verCount = 0;
        let invCount = 0;

        const day = lastDate.getDate();
        const month = lastDate.getMonth();
        const year = lastDate.getFullYear();

        const rowsToday = sorted.filter(r => {
          const d = new Date(r[timeCol]);
          return !isNaN(d.getTime()) &&
                 d.getDate() === day &&
                 d.getMonth() === month &&
                 d.getFullYear() === year;
        });

        rowsToday.forEach(r => {
          const raw = String(r[modeCol] || "").toUpperCase();
          if (raw.includes("AUTO") || raw === "0") {
            autoCount++;
          } else if (raw.includes("MANUAL VER")) {
            verCount++;
          } else if (raw.includes("MANUAL INV")) {
            invCount++;
          }
        });

        const autoHours = autoCount * stepHours;
        const verHours = verCount * stepHours;
        const invHours = invCount * stepHours;

        modeLoadLabel.textContent =
          `Auto: ${autoHours.toFixed(1)} h · Verano man.: ${verHours.toFixed(1)} h · Invierno man.: ${invHours.toFixed(1)} h`;
      }

      // HUMEDAD INTERNA (hum_invernadero_rel)
      const humCol = cols.find(c => ["hum_invernadero_rel", "humedad", "humidity"].includes(c));
      if (humCol) {
        let lastHum = null;
        const humVals = [];
        rows.forEach(r => {
          const raw = r[humCol];
          if (raw === undefined || raw === null) return;
          const v = Number(raw);
          if (!isNaN(v)) {
            humVals.push(v);
            lastHum = v;
          }
        });

        const humValueLabel = document.getElementById("statusHum");
        const humRangeLabel = document.getElementById("statusHumRange");
        const humBarFill = document.getElementById("humBarFill");

        if (humValueLabel) {
          humValueLabel.textContent =
            (lastHum !== null && !isNaN(lastHum)) ? lastHum.toFixed(1) + " %" : "-- %";
        }

        if (humRangeLabel) {
          if (humVals.length) {
            const minH = Math.min(...humVals);
            const maxH = Math.max(...humVals);
            humRangeLabel.textContent =
              `Mín: ${minH.toFixed(1)} % · Máx: ${maxH.toFixed(1)} %`;
          } else {
            humRangeLabel.textContent = "Mín: -- % · Máx: -- %";
          }
        }

        if (humBarFill) {
          let pct = (lastHum !== null && !isNaN(lastHum)) ? lastHum : 0;
          if (pct < 0) pct = 0;
          if (pct > 100) pct = 100;
          humBarFill.style.width = pct + "%";
        }
      }

    }

    function updateStatusFromData() {
      if (!globalData || !globalData.rows || !globalData.rows.length) return;
      const rows = globalData.rows;
      const cols = globalData.columns || [];
      const timeCols = globalData.datetimeColumns || [];

      const timeCol = timeCols.includes("timestamp")
        ? "timestamp"
        : (timeCols[0] || null);

      let lastRow = rows[rows.length - 1];
      if (timeCol) {
        const sorted = [...rows].filter(r => r[timeCol]).sort((a, b) => {
          return new Date(a[timeCol]) - new Date(b[timeCol]);
        });
        if (sorted.length) lastRow = sorted[sorted.length - 1];
      }

      const tempCol = cols.find(c => ["temp_invernadero_C", "tempC", "temperatura"].includes(c));
      const modeCol = cols.find(c => ["modo_control", "modo", "controlMode"].includes(c));
      const stationCol = cols.find(c => ["estacion", "estación"].includes(c));
      const wallCols = cols.filter(c => ["vent_pared_on", "relay_pared_on", "wallFansOn"].includes(c));
      const colgCols = cols.filter(c => ["vent_colg_on", "n_colg_vent_on", "colgFansOn"].includes(c));
      const vfdFreqCol = cols.find(c => ["vfd_freq_out_Hz", "freq_cmd_Hz"].includes(c));
      const vfdVoltCol = cols.find(c => ["vfd_volt_out_V"].includes(c));
      const vfdCurrCol = cols.find(c => ["vfd_curr_out_A"].includes(c));

      const tempVal = tempCol ? Number(lastRow[tempCol]) : null;
      document.getElementById("statusTemp").textContent =
        (tempVal !== null && !isNaN(tempVal)) ? tempVal.toFixed(1) + " °C" : "-- °C";

      const modeRaw = modeCol ? String(lastRow[modeCol] || "") : "";
      let modeLabel = "—";
      let modeDesc = "";
      const modeUpper = modeRaw.toUpperCase();
      if (modeUpper.includes("AUTO") || modeRaw === "0") {
        modeLabel = "Automático";
        modeDesc = "El sistema decide estación y frecuencia según la fecha y la temperatura.";
      } else if (modeUpper.includes("MANUAL VER")) {
        modeLabel = "Verano manual";
        modeDesc = "Forzado a lógica de verano, sin importar el mes del RTC.";
      } else if (modeUpper.includes("MANUAL INV")) {
        modeLabel = "Invierno manual";
        modeDesc = "Forzado a lógica de invierno, sin importar el mes del RTC.";
      } else if (modeRaw) {
        modeLabel = modeRaw;
        modeDesc = "Modo personalizado desde el controlador.";
      } else {
        modeDesc = "Sin información del modo de control.";
      }
      document.getElementById("statusMode").textContent = modeLabel;
      document.getElementById("statusModeDesc").textContent = modeDesc;

      const stationVal = stationCol ? String(lastRow[stationCol] || "") : "";
      const labelStation = document.getElementById("labelStation");
      const dotStation = document.getElementById("dotStation");
      const chipStation = document.getElementById("chipStation");
      if (labelStation) {
        labelStation.textContent = "Estación: " + (stationVal || "--");
      }
      if (chipStation && dotStation) {
        chipStation.classList.add("on");
        dotStation.classList.add("on");
      }

      const wallStateVal = wallCols.length ? Number(lastRow[wallCols[0]]) : null;
      const wallOn = wallStateVal === 1 || wallStateVal === true;
      document.getElementById("statusWall").textContent = wallOn ? "ON" : "OFF";
      setOnOffChip("chipWall", "dotWall", "labelWall", wallOn, "Activados", "Apagados");

      let colgOn = false;
      let nColg = null;
      if (colgCols.length) {
        const base = Number(lastRow[colgCols[0]]);
        if (!isNaN(base)) {
          nColg = base;
          colgOn = base > 0;
        }
      }
      document.getElementById("statusColg").textContent = colgOn ? "ON" : "OFF";
      const detail = document.getElementById("statusColgDetail");
      if (detail) {
        if (nColg !== null) {
          detail.textContent = `Ventiladores activos: ${nColg} de 4 posibles.`;
        } else {
          detail.textContent = "Ventiladores colgantes sin dato de conteo.";
        }
      }
      setOnOffChip("chipColg", "dotColg", "labelColg", colgOn, "Activados", "Apagados");

      const vfdFreq = vfdFreqCol ? Number(lastRow[vfdFreqCol]) : null;
      document.getElementById("statusVfdFreq").textContent =
        (vfdFreq !== null && !isNaN(vfdFreq)) ? vfdFreq.toFixed(1) + " Hz" : "-- Hz";

      const vfdVolt = vfdVoltCol ? Number(lastRow[vfdVoltCol]) : null;
      document.getElementById("statusVfdVolt").textContent =
        (vfdVolt !== null && !isNaN(vfdVolt)) ? vfdVolt.toFixed(0) + " V" : "-- V";

      const vfdCurr = vfdCurrCol ? Number(lastRow[vfdCurrCol]) : null;
      document.getElementById("statusVfdCurr").textContent =
        (vfdCurr !== null && !isNaN(vfdCurr)) ? vfdCurr.toFixed(2) + " A" : "-- A";

      // Estado de bomba / nebulización
      const pumpCol = cols.find(c => ["pump_on"].includes(c));
      if (pumpCol) {
        const rawPump = lastRow[pumpCol];
        const pumpOn = Number(rawPump) === 1 || rawPump === true;
        const pumpLabel = document.getElementById("statusPump");
        if (pumpLabel) {
          pumpLabel.textContent = pumpOn ? "ON" : "OFF";
        }
        setOnOffChip("chipPump", "dotPump", "labelPump", pumpOn, "Encendida", "Apagada");
      }

      let tsText = "--";
      if (timeCol && lastRow[timeCol]) {
        const d = new Date(lastRow[timeCol]);
        if (!isNaN(d.getTime())) {
          tsText = d.toLocaleString();
          const hour = d.getHours();
          const isDay = hour >= 7 && hour < 19;
          const chip = document.getElementById("chipDayNight");
          const dot = document.getElementById("dotDayNight");
          const label = document.getElementById("labelDayNight");
          if (isDay) {
            chip.classList.add("on");
            dot.classList.add("on");
            label.textContent = "Día (RTC)";
          } else {
            chip.classList.remove("on");
            dot.classList.remove("on");
            label.textContent = "Noche (RTC)";
          }
        }
      }
      document.getElementById("statusLastTs").textContent = tsText;

      updateTemperatureVisuals();
      updateSummaryWidgets();
    }


    function updateControlStatusFromData() {
      if (!globalData || !globalData.rows || !globalData.rows.length) return;
      const rows = globalData.rows;
      const cols = globalData.columns || [];
      const timeCols = globalData.datetimeColumns || [];

      const timeCol = timeCols.includes("timestamp")
        ? "timestamp"
        : (timeCols[0] || null);

      let lastRow = rows[rows.length - 1];
      if (timeCol) {
        const sorted = [...rows].filter(r => r[timeCol]).sort((a, b) => {
          return new Date(a[timeCol]) - new Date(b[timeCol]);
        });
        if (sorted.length) lastRow = sorted[sorted.length - 1];
      }

      const wallCol = cols.find(c => ["vent_pared_on", "relay_pared_on", "wallFansOn"].includes(c));
      const colgStateCol = cols.find(c => ["vent_colg_on", "colgFansOn"].includes(c));
      const colgCountCol = cols.find(c => ["n_colg_vent_on"].includes(c));
      const colgRefCol = cols.find(c => ["colg_ref_unidades"].includes(c));
      const pumpCol = cols.find(c => ["pump_on"].includes(c));
      const freqCol = cols.find(c => ["freq_cmd_Hz", "vfd_freq_out_Hz"].includes(c));

      const wallStateLabel = document.getElementById("ctrlWallState");
      if (wallStateLabel) {
        let txt = "Estado actual: --";
        if (wallCol && lastRow[wallCol] !== undefined && lastRow[wallCol] !== null) {
          const on = Number(lastRow[wallCol]) > 0;
          txt = "Estado actual: " + (on ? "ON" : "OFF");
        }
        wallStateLabel.textContent = txt;
      }

      const colgStateLabel = document.getElementById("ctrlColgState");
      const colgDetailLabel = document.getElementById("ctrlColgDetail");
      if (colgStateLabel) {
        let on = false;
        if (colgStateCol && lastRow[colgStateCol] !== undefined && lastRow[colgStateCol] !== null) {
          on = Number(lastRow[colgStateCol]) > 0;
        }
        colgStateLabel.textContent = "Estado actual: " + (on ? "ON" : "OFF");
      }
      if (colgDetailLabel) {
        const ref = colgRefCol && lastRow[colgRefCol] != null ? Number(lastRow[colgRefCol]) : null;
        const cnt = colgCountCol && lastRow[colgCountCol] != null ? Number(lastRow[colgCountCol]) : null;
        const freq = freqCol && lastRow[freqCol] != null ? Number(lastRow[freqCol]) : null;
        let txt = "Cantidad objetivo / real: --";
        if (!isNaN(ref) || !isNaN(cnt)) {
          txt = "Cantidad objetivo / real: " +
            (isNaN(ref) ? "--" : ref.toFixed(1)) + " / " +
            (isNaN(cnt) ? "--" : cnt.toFixed(0));
        }
        if (!isNaN(freq)) {
          txt += ` · Frecuencia: ${freq.toFixed(1)} Hz`;
        }
        colgDetailLabel.textContent = txt;
      }

      const pumpStateLabel = document.getElementById("ctrlPumpState");
      if (pumpStateLabel) {
        let txt = "Estado actual: --";
        if (pumpCol && lastRow[pumpCol] !== undefined && lastRow[pumpCol] !== null) {
          const on = Number(lastRow[pumpCol]) > 0;
          txt = "Estado actual: " + (on ? "ON" : "OFF");
        }
        pumpStateLabel.textContent = txt;
      }
    }

    async function loadControlState() {
      try {
        const resp = await fetch("/api/control_state");
        if (!resp.ok) return;
        const data = await resp.json();
        const map = {
          ctrlWallManual: "wall_manual",
          ctrlWallOn: "wall_on",
          ctrlColgManual: "colg_manual",
          ctrlColgOn: "colg_on",
          ctrlPumpManual: "pump_manual",
          ctrlPumpOn: "pump_on",
        };
        Object.keys(map).forEach(id => {
          const el = document.getElementById(id);
          if (el && typeof data[map[id]] === "boolean") {
            el.checked = data[map[id]];
          }
        });
      } catch (e) {
        console.error("Error al cargar control_state", e);
      }
    }

    async function applyControlState() {
      const statusMsg = document.getElementById("ctrlStatusMsg");
      const payload = {
        wall_manual: document.getElementById("ctrlWallManual")?.checked || false,
        wall_on: document.getElementById("ctrlWallOn")?.checked || false,
        colg_manual: document.getElementById("ctrlColgManual")?.checked || false,
        colg_on: document.getElementById("ctrlColgOn")?.checked || false,
        pump_manual: document.getElementById("ctrlPumpManual")?.checked || false,
        pump_on: document.getElementById("ctrlPumpOn")?.checked || false,
      };
      try {
        const resp = await fetch("/api/control_state", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        if (!resp.ok) {
          if (statusMsg) statusMsg.textContent = "Error al enviar el control.";
          return;
        }
        await resp.json();
        if (statusMsg) statusMsg.textContent = "Control enviado correctamente.";
      } catch (e) {
        console.error("Error al aplicar control", e);
        if (statusMsg) statusMsg.textContent = "Error de red al enviar el control.";
      }
    }

    function renderTable() {
      const wrapper = document.getElementById("tableWrapper");
      wrapper.innerHTML = "";
      if (!globalData || !globalData.rows || !globalData.rows.length) {
        wrapper.innerHTML = '<div class="empty-state" style="padding:16px;">Sin datos para mostrar.</div>';
        return;
      }
      const cols = globalData.columns || [];
      const labels = globalData.fieldFriendlyLabels || {};
      const rows = globalData.rows;
      const maxRows = Math.min(rows.length, 300);

      let html = "<table><thead><tr>";
      cols.forEach(c => {
        html += "<th>" + (labels[c] || c) + "</th>";
      });
      html += "</tr></thead><tbody>";

      for (let i = 0; i < maxRows; i++) {
        const r = rows[i];
        html += "<tr>";
        cols.forEach(c => {
          let v = r[c];
          if (v === null || v === undefined) v = "";
          html += "<td>" + v + "</td>";
        });
        html += "</tr>";
      }
      if (rows.length > maxRows) {
        html += '<tr><td colspan="' + cols.length + '">… (' + (rows.length - maxRows) + ' filas adicionales no mostradas)</td></tr>';
      }
      html += "</tbody></table>";
      wrapper.innerHTML = html;
    }

    function renderFieldsDictionary() {
      const container = document.getElementById("fieldsGrid");
      container.innerHTML = "";
      if (!globalData || !globalData.columns) return;
      const cols = globalData.columns;
      const labels = globalData.fieldFriendlyLabels || {};
      const descs = globalData.fieldDescriptions || {};

      cols.forEach(c => {
        const card = document.createElement("div");
        card.className = "field-card";
        const label = labels[c] || c;
        const desc = descs[c] || ("Campo registrado: " + label);
        card.innerHTML = `
          <div class="field-name">${c}</div>
          <div class="field-label">${label}</div>
          <div class="field-desc">${desc}</div>
        `;
        container.appendChild(card);
      });
    }

    function resetFilters() {
      const from = document.getElementById("fromDate");
      const to = document.getElementById("toDate");
      if (from) from.value = "";
      if (to) to.value = "";
      currentFilter = "all";
      applyFilterButtons();
      if (globalData) {
        initControls();
        updateChart();
      }
    }

    function setupTabs() {
      const tabs = document.querySelectorAll(".tab");
      const panels = document.querySelectorAll(".tab-panel");
      tabs.forEach(tab => {
        tab.addEventListener("click", () => {
          const target = tab.getAttribute("data-tab");
          tabs.forEach(t => t.classList.remove("active"));
          tab.classList.add("active");
          panels.forEach(p => {
            if (p.id === "tab-" + target) p.classList.add("active");
            else p.classList.remove("active");
          });
        });
      });
    }

    document.addEventListener("DOMContentLoaded", () => {
      document.getElementById("btnUpload").addEventListener("click", uploadFile);
      document.getElementById("btnReset").addEventListener("click", resetFilters);

      const btnExport = document.getElementById("btnExportXlsx");
      if (btnExport) btnExport.addEventListener("click", exportXlsx);
      const btnApplyControl = document.getElementById("btnApplyControl");
      if (btnApplyControl) btnApplyControl.addEventListener("click", function(e) { e.preventDefault(); applyControlState(); });
      loadControlState();

      const selY1 = document.getElementById("selectY1");
      const selY2 = document.getElementById("selectY2");
      const selTime = document.getElementById("selectTime");
      const from = document.getElementById("fromDate");
      const to = document.getElementById("toDate");

      if (selY1) selY1.addEventListener("change", () => { updateChart(); updateTemperatureVisuals(); });
      if (selY2) selY2.addEventListener("change", updateChart);
      if (selTime) selTime.addEventListener("change", () => { updateChart(); updateTemperatureVisuals(); });
      if (from) from.addEventListener("change", () => { updateChart(); updateTemperatureVisuals(); });
      if (to) to.addEventListener("change", () => { updateChart(); updateTemperatureVisuals(); });

      ["fltAll","fltDay","fltNight"].forEach(id => {
        const btn = document.getElementById(id);
        if (!btn) return;
        btn.addEventListener("click", () => {
          const filter = btn.getAttribute("data-filter");
          currentFilter = filter;
          applyFilterButtons();
          updateChart();
        });
      });

      setupTabs();
      setEmptyState(true);
      applyFilterButtons();
      loadData();
    });
  </script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def index():
    return HTMLResponse(DASHBOARD_HTML)


@app.post("/upload")
async def upload_excel(
    file: UploadFile = File(...),
    mode: str = Query("replace", regex="^(replace|append)$")
):
    """
    Sube un Excel y lo guarda en memoria.
    mode = replace → reemplaza LAST_DF
    mode = append  → concatena con LAST_DF
    """
    global LAST_DF
    try:
        content = await file.read()
        excel_bytes = BytesIO(content)
        df_new = pd.read_excel(excel_bytes)

        # Parseo automático de columnas fecha/hora
        for col in df_new.columns:
            if df_new[col].dtype == object:
                try:
                    parsed = pd.to_datetime(df_new[col])
                    if parsed.notna().mean() > 0.5:
                        df_new[col] = parsed
                except Exception:
                    continue

        if LAST_DF is None or mode == "replace":
            LAST_DF = df_new
        else:
            LAST_DF = pd.concat([LAST_DF, df_new], ignore_index=True)

        return {
            "status": "ok",
            "filename": file.filename,
            "rows": int(len(LAST_DF)),
            "columns": list(LAST_DF.columns),
        }
    except Exception as e:
        return JSONResponse(
            {"detail": f"Error al procesar el archivo: {e}"},
            status_code=400,
        )


@app.get("/api/data")
async def get_data():
    global LAST_DF
    if LAST_DF is None:
        return JSONResponse(
            {"detail": "No hay datos cargados aún."},
            status_code=404,
        )

    df = LAST_DF.copy()

    numeric_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    datetime_cols = [c for c in df.columns if pd.api.types.is_datetime64_any_dtype(df[c])]

    field_labels = {}
    field_descriptions = {}

    for c in df.columns:
        pretty = prettify_column_name(c)
        field_labels[c] = pretty
        desc = KNOWN_FIELD_DESCRIPTIONS.get(c)
        if desc is None:
            desc = f"Campo registrado: {pretty}."
        field_descriptions[c] = desc

    data_rows = []
    for _, row in df.iterrows():
        record = {}
        for c in df.columns:
            val = row[c]
            if pd.isna(val):
                record[c] = None
            elif c in datetime_cols:
                record[c] = val.isoformat()
            else:
                record[c] = val.item() if hasattr(val, "item") else val
        data_rows.append(record)

    return {
        "columns": list(df.columns),
        "numericColumns": numeric_cols,
        "datetimeColumns": datetime_cols,
        "fieldFriendlyLabels": field_labels,
        "fieldDescriptions": field_descriptions,
        "rows": data_rows,
    }

# ===================== API ESP32 / GSM =====================

class Lectura(BaseModel):
    timestamp: str
    dia_semana: str
    modo_control: str
    estacion: str
    temp_invernadero_C: float
    hum_invernadero_rel: Optional[float] = None
    freq_ref_Hz: float
    freq_cmd_Hz: float
    colg_ref_unidades: float
    n_colg_vent_on: int
    relay_pared_on: int
    relay_colg_1_on: int
    relay_colg_2_on: int
    vent_pared_on: int
    vent_colg_on: int
    vfd_freq_out_Hz: float
    vfd_volt_out_V: float
    vfd_curr_out_A: float
    pump_on: int
    pump_auto_mode: int


CONTROL_STATE: Dict[str, bool] = {
    "wall_manual": False,
    "wall_on": False,
    "colg_manual": False,
    "colg_on": False,
    "pump_manual": False,
    "pump_on": False,
}


class ControlUpdate(BaseModel):
    wall_manual: Optional[bool] = None
    wall_on: Optional[bool] = None
    colg_manual: Optional[bool] = None
    colg_on: Optional[bool] = None
    pump_manual: Optional[bool] = None
    pump_on: Optional[bool] = None


@app.post("/api/ingreso")
async def api_ingreso(lectura: Lectura):
    """
    Endpoint que usará el ESP32 (vía SIM/GSM) para enviar cada registro de telemetría.
    Los datos se guardan en memoria en LAST_DF para visualización inmediata.
    """
    global LAST_DF
    rec = lectura.dict()
    new_df = pd.DataFrame([rec])
    if LAST_DF is None:
        LAST_DF = new_df
    else:
        LAST_DF = pd.concat([LAST_DF, new_df], ignore_index=True)
    return {"status": "ok"}


@app.get("/api/last")
async def api_last():
    """
    Devuelve el último registro disponible según el DataFrame in-memory LAST_DF.
    """
    global LAST_DF
    if LAST_DF is None or LAST_DF.empty:
        return JSONResponse({"detail": "No hay datos aún"}, status_code=404)

    df = LAST_DF
    last_row = df.iloc[-1]
    datetime_cols = [c for c in df.columns if pd.api.types.is_datetime64_any_dtype(df[c])]

    record = {}
    for c in df.columns:
        val = last_row[c]
        if pd.isna(val):
            record[c] = None
        elif c in datetime_cols:
            record[c] = val.isoformat()
        else:
            record[c] = val.item() if hasattr(val, "item") else val

    return record


@app.get("/api/control_state")
async def get_control_state():
    """
    Devuelve el estado actual de los flags de control remoto
    (pared, colgantes, bomba), que el ESP32 consultará periódicamente.
    """
    return CONTROL_STATE


@app.post("/api/control_state")
async def update_control_state(update: ControlUpdate):
    """
    Actualiza parcialmente el estado de control remoto.
    Sólo los campos presentes en el body son modificados.
    """
    data = update.dict(exclude_unset=True)
    for k, v in data.items():
        if k in CONTROL_STATE and isinstance(v, bool):
            CONTROL_STATE[k] = v
    return CONTROL_STATE


