from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import sqlite3
from pathlib import Path

DB_PATH = Path("invernadero.db")

app = FastAPI(title="Dashboard Invernadero ADTEC")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ===================== BASE DE DATOS =====================

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS lecturas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            dia_semana TEXT,
            modo_control TEXT,
            estacion TEXT,
            temp_invernadero_C REAL,
            freq_ref_Hz REAL,
            freq_cmd_Hz REAL,
            colg_ref_unidades REAL,
            n_colg_vent_on INTEGER,
            relay_pared_on INTEGER,
            relay_colg_1_on INTEGER,
            relay_colg_2_on INTEGER,
            vent_pared_on INTEGER,
            vent_colg_on INTEGER,
            vfd_freq_out_Hz REAL,
            vfd_volt_out_V REAL,
            vfd_curr_out_A REAL,
            pump_on INTEGER,
            pump_auto_mode INTEGER
        )
        """
    )
    conn.commit()
    conn.close()


init_db()


# ===================== MODELOS Pydantic =====================

class Lectura(BaseModel):
    timestamp: str
    dia_semana: Optional[str] = None
    modo_control: Optional[str] = None
    estacion: Optional[str] = None
    temp_invernadero_C: Optional[float] = None
    freq_ref_Hz: Optional[float] = None
    freq_cmd_Hz: Optional[float] = None
    colg_ref_unidades: Optional[float] = None
    n_colg_vent_on: Optional[int] = None
    relay_pared_on: Optional[int] = None
    relay_colg_1_on: Optional[int] = None
    relay_colg_2_on: Optional[int] = None
    vent_pared_on: Optional[int] = None
    vent_colg_on: Optional[int] = None
    vfd_freq_out_Hz: Optional[float] = None
    vfd_volt_out_V: Optional[float] = None
    vfd_curr_out_A: Optional[float] = None
    pump_on: Optional[int] = None          # 0/1
    pump_auto_mode: Optional[int] = None   # 1 = auto, 0 = manual


class ControlUpdate(BaseModel):
    wall_manual: Optional[bool] = None
    wall_on: Optional[bool] = None
    colg_manual: Optional[bool] = None
    colg_on: Optional[bool] = None
    pump_manual: Optional[bool] = None
    pump_on: Optional[bool] = None


# ===================== ESTADO DE CONTROL REMOTO =====================

control_state: Dict[str, bool] = {
    "wall_manual": False,
    "wall_on": False,
    "colg_manual": False,
    "colg_on": False,
    "pump_manual": False,
    "pump_on": False,
}


# ===================== ENDPOINTS API =====================

@app.post("/api/ingreso")
async def api_ingreso(lectura: Lectura):
    """
    Endpoint que usará el ESP32 (vía SIM) para enviar
    cada registro de telemetría.
    """
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO lecturas (
            timestamp, dia_semana, modo_control, estacion,
            temp_invernadero_C, freq_ref_Hz, freq_cmd_Hz,
            colg_ref_unidades, n_colg_vent_on,
            relay_pared_on, relay_colg_1_on, relay_colg_2_on,
            vent_pared_on, vent_colg_on,
            vfd_freq_out_Hz, vfd_volt_out_V, vfd_curr_out_A,
            pump_on, pump_auto_mode
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            lectura.timestamp,
            lectura.dia_semana,
            lectura.modo_control,
            lectura.estacion,
            lectura.temp_invernadero_C,
            lectura.freq_ref_Hz,
            lectura.freq_cmd_Hz,
            lectura.colg_ref_unidades,
            lectura.n_colg_vent_on,
            lectura.relay_pared_on,
            lectura.relay_colg_1_on,
            lectura.relay_colg_2_on,
            lectura.vent_pared_on,
            lectura.vent_colg_on,
            lectura.vfd_freq_out_Hz,
            lectura.vfd_volt_out_V,
            lectura.vfd_curr_out_A,
            lectura.pump_on,
            lectura.pump_auto_mode,
        ),
    )
    conn.commit()
    conn.close()
    return {"status": "ok"}



# ===================== HTML DASHBOARD =====================

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang=\"es\">
<head>
  <meta charset=\"UTF-8\">
  <title>Invernadero ADTEC - Dashboard</title>
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">
  <style>
    :root {
      --bg: #020617;
      --card: #0f172a;
      --card-soft: #020617;
      --accent: #22c55e;
      --accent-soft: rgba(34, 197, 94, 0.2);
      --accent-red: #ef4444;
      --accent-blue: #0ea5e9;
      --text-main: #e5e7eb;
      --text-soft: #9ca3af;
      --border-subtle: rgba(148, 163, 184, 0.3);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: system-ui, -apple-system, BlinkMacSystemFont, \"Segoe UI\", sans-serif;
      background: radial-gradient(circle at top, #0b1120 0, #020617 55%);
      color: var(--text-main);
    }
    .shell {
      max-width: 1200px;
      margin: 0 auto;
      padding: 16px;
    }
    header {
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      align-items: center;
      gap: 16px;
      margin-bottom: 16px;
    }
    .logo {
      display: flex;
      align-items: center;
      gap: 12px;
    }
    .logo-icon {
      width: 40px;
      height: 40px;
      border-radius: 12px;
      background: radial-gradient(circle at 30% 30%, #facc15, #22c55e);
      box-shadow: 0 0 25px rgba(250, 204, 21, 0.7);
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 700;
      color: #020617;
    }
    .logo-text-title {
      font-size: 1.2rem;
      font-weight: 600;
    }
    .logo-text-sub {
      font-size: 0.8rem;
      color: var(--text-soft);
    }

    .tabs {
      display: flex;
      gap: 8px;
      margin-bottom: 16px;
      flex-wrap: wrap;
    }
    .tab-btn {
      border-radius: 999px;
      border: 1px solid transparent;
      padding: 6px 14px;
      cursor: pointer;
      background: rgba(15, 23, 42, 0.8);
      color: var(--text-soft);
      font-size: 0.9rem;
      display: inline-flex;
      align-items: center;
      gap: 6px;
    }
    .tab-btn.active {
      background: rgba(34, 197, 94, 0.16);
      color: #bbf7d0;
      border-color: rgba(34, 197, 94, 0.6);
    }

    .grid {
      display: grid;
      grid-template-columns: repeat(12, minmax(0, 1fr));
      gap: 16px;
    }
    @media (max-width: 900px) {
      .grid {
        grid-template-columns: repeat(1, minmax(0, 1fr));
      }
    }
    .card {
      background: linear-gradient(135deg, #020617, #020617 45%, #0f172a);
      border-radius: 16px;
      border: 1px solid var(--border-subtle);
      padding: 16px;
      box-shadow: 0 18px 40px rgba(15, 23, 42, 0.8);
    }
    .card-emphasis {
      grid-column: span 6;
      min-height: 180px;
    }
    .card-status {
      grid-column: span 3;
      min-height: 140px;
    }
    .card-full {
      grid-column: span 12;
    }
    @media (max-width: 900px) {
      .card-emphasis, .card-status, .card-full {
        grid-column: span 1;
      }
    }

    .card-title {
      font-size: 0.9rem;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--text-soft);
      margin-bottom: 6px;
    }
    .value-main {
      font-size: 2.6rem;
      font-weight: 600;
      margin: 6px 0;
    }
    .value-unit {
      font-size: 1rem;
      color: var(--text-soft);
    }
    .chip {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      border-radius: 999px;
      padding: 4px 10px;
      background: rgba(15, 23, 42, 0.9);
      border: 1px solid rgba(148, 163, 184, 0.4);
      font-size: 0.75rem;
      color: var(--text-soft);
    }
    .chip-ok {
      border-color: rgba(34, 197, 94, 0.7);
      color: #bbf7d0;
      background: rgba(22, 163, 74, 0.16);
    }
    .chip-bad {
      border-color: rgba(248, 113, 113, 0.9);
      color: #fecaca;
      background: rgba(127, 29, 29, 0.4);
    }

    .pill {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      border-radius: 999px;
      padding: 4px 11px;
      background: rgba(15, 23, 42, 0.8);
      border: 1px solid rgba(148, 163, 184, 0.4);
      font-size: 0.78rem;
      color: var(--text-soft);
    }

    /* CONTROL */
    .control-layout {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 16px;
    }
    @media (max-width: 900px) {
      .control-layout {
        grid-template-columns: repeat(1, minmax(0, 1fr));
      }
    }
    .control-card-title {
      font-size: 1rem;
      margin-bottom: 8px;
    }
    .control-state {
      font-size: 1.2rem;
      margin-bottom: 6px;
    }
    .btn-row {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 6px;
    }
    .btn {
      border-radius: 999px;
      padding: 6px 14px;
      border: 1px solid transparent;
      cursor: pointer;
      font-size: 0.9rem;
      background: rgba(15, 23, 42, 0.8);
      color: var(--text-soft);
    }
    .btn-on {
      background: rgba(34, 197, 94, 0.2);
      color: #bbf7d0;
      border-color: rgba(34, 197, 94, 0.7);
    }
    .btn-off {
      background: rgba(248, 113, 113, 0.12);
      color: #fecaca;
      border-color: rgba(248, 113, 113, 0.7);
    }
    .btn-mode {
      background: rgba(56, 189, 248, 0.16);
      color: #e0f2fe;
      border-color: rgba(56, 189, 248, 0.7);
    }

    .muted {
      color: var(--text-soft);
      font-size: 0.8rem;
    }
    .status-dot {
      width: 9px;
      height: 9px;
      border-radius: 999px;
      background: #22c55e;
      box-shadow: 0 0 10px rgba(34, 197, 94, 0.8);
    }
    .status-dot.off {
      background: #4b5563;
      box-shadow: none;
    }

    .small-label {
      font-size: 0.8rem;
      color: var(--text-soft);
    }
  </style>
</head>
<body>
  <div class=\"shell\">
    <header>
      <div class=\"logo\">
        <div class=\"logo-icon\">A</div>
        <div>
          <div class=\"logo-text-title\">ADTEC Invernadero</div>
          <div class=\"logo-text-sub\">Control térmico · Ventilación · Nebulización</div>
        </div>
      </div>
      <div style=\"display:flex; flex-direction:column; align-items:flex-end; gap:4px;\">
        <div class=\"chip\" id=\"chipTime\">Sin datos aún</div>
        <div class=\"muted\" id=\"chipMeta\">Esperando primera telemetría...</div>
      </div>
    </header>

    <div class=\"tabs\">
      <button class=\"tab-btn active\" data-tab=\"dashboard\">📊 Dashboard</button>
      <button class=\"tab-btn\" data-tab=\"control\">🎛️ Control</button>
    </div>

    <div id=\"tab-dashboard\">
      <div class=\"grid\">
        <div class=\"card card-emphasis\">
          <div class=\"card-title\">Temperatura invernadero</div>
          <div class=\"value-main\">
            <span id=\"tempValue\">--.-</span><span class=\"value-unit\"> °C</span>
          </div>
          <div style=\"display:flex; gap:8px; flex-wrap:wrap; margin-top:8px;\">
            <span class=\"pill\" id=\"pillEstacion\">Estación: --</span>
            <span class=\"pill\" id=\"pillModo\">Modo control: --</span>
          </div>
          <div class=\"muted\" style=\"margin-top:10px;\" id=\"tempHint\">
            Sin datos de temperatura.
          </div>
        </div>

        <div class=\"card card-status\">
          <div class=\"card-title\">Ventiladores pared</div>
          <div class=\"control-state\">
            <span id=\"wallStateLabel\">--</span>
          </div>
          <div class=\"muted small-label\">
            Frecuencia comando: <span id=\"freqCmdLabel\">-- Hz</span><br>
            Frecuencia salida VFD: <span id=\"freqOutLabel\">-- Hz</span>
          </div>
          <div style=\"margin-top:8px;\">
            <span id=\"chipWall\" class=\"chip\">Estado: --</span>
          </div>
        </div>

        <div class=\"card card-status\">
          <div class=\"card-title\">Ventiladores colgantes</div>
          <div class=\"control-state\">
            <span id=\"colgStateLabel\">--</span>
          </div>
          <div class=\"muted small-label\">
            Objetivo colgantes: <span id=\"colgRefLabel\">--</span><br>
            Activos reportados: <span id=\"colgOnLabel\">--</span>
          </div>
          <div style=\"margin-top:8px;\">
            <span id=\"chipColg\" class=\"chip\">Estado: --</span>
          </div>
        </div>

        <div class=\"card card-status\">
          <div class=\"card-title\">Bomba / Nebulización</div>
          <div style=\"display:flex; align-items:center; gap:8px;\">
            <div class=\"status-dot\" id=\"pumpDot\"></div>
            <div class=\"control-state\" id=\"pumpStateLabel\">--</div>
          </div>
          <div class=\"muted small-label\">
            Modo riego: <span id=\"pumpModeLabel\">--</span>
          </div>
        </div>

        <div class=\"card card-full\">
          <div class=\"card-title\">Resumen rápido</div>
          <div class=\"muted\" id=\"summaryText\">
            Sin datos aún.
          </div>
        </div>
      </div>
    </div>

    <div id=\"tab-control\" style=\"display:none;\">
      <div class=\"card card-full\">
        <div class=\"card-title\">Control remoto</div>
        <p class=\"muted\">
          Estos comandos se guardan en la API. Para que afecten al invernadero,
          el ESP32 debe consultar periódicamente <code>/api/control_state</code>
          y aplicar los cambios.
        </p>
        <div class=\"control-layout\" style=\"margin-top:10px;\">
          <div class=\"card\">
            <div class=\"control-card-title\">Ventiladores de pared</div>
            <div class=\"control-state\" id=\"ctlWallState\">--</div>
            <div class=\"muted small-label\" id=\"ctlWallMode\">Modo: --</div>
            <div class=\"btn-row\">
              <button class=\"btn btn-mode\" onclick=\"setControl({wall_manual:false})\">Auto</button>
              <button class=\"btn btn-mode\" onclick=\"setControl({wall_manual:true})\">Manual</button>
              <button class=\"btn btn-on\" onclick=\"setControl({wall_on:true, wall_manual:true})\">ON</button>
              <button class=\"btn btn-off\" onclick=\"setControl({wall_on:false, wall_manual:true})\">OFF</button>
            </div>
          </div>
          <div class=\"card\">
            <div class=\"control-card-title\">Ventiladores colgantes</div>
            <div class=\"control-state\" id=\"ctlColgState\">--</div>
            <div class=\"muted small-label\" id=\"ctlColgMode\">Modo: --</div>
            <div class=\"btn-row\">
              <button class=\"btn btn-mode\" onclick=\"setControl({colg_manual:false})\">Auto</button>
              <button class=\"btn btn-mode\" onclick=\"setControl({colg_manual:true})\">Manual</button>
              <button class=\"btn btn-on\" onclick=\"setControl({colg_on:true, colg_manual:true})\">ON</button>
              <button class=\"btn btn-off\" onclick=\"setControl({colg_on:false, colg_manual:true})\">OFF</button>
            </div>
          </div>
          <div class=\"card\">
            <div class=\"control-card-title\">Bomba / Nebulización</div>
            <div class=\"control-state\" id=\"ctlPumpState\">--</div>
            <div class=\"muted small-label\" id=\"ctlPumpMode\">Modo: --</div>
            <div class=\"btn-row\">
              <button class=\"btn btn-mode\" onclick=\"setControl({pump_manual:false})\">Auto</button>
              <button class=\"btn btn-mode\" onclick=\"setControl({pump_manual:true})\">Manual</button>
              <button class=\"btn btn-on\" onclick=\"setControl({pump_on:true, pump_manual:true})\">ON</button>
              <button class=\"btn btn-off\" onclick=\"setControl({pump_on:false, pump_manual:true})\">OFF</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>

<script>
  const tabButtons = document.querySelectorAll(".tab-btn");
  const tabDashboard = document.getElementById("tab-dashboard");
  const tabControl = document.getElementById("tab-control");

  tabButtons.forEach(btn => {
    btn.addEventListener("click", () => {
      tabButtons.forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      const tab = btn.dataset.tab;
      if (tab === "dashboard") {
        tabDashboard.style.display = "";
        tabControl.style.display = "none";
      } else {
        tabDashboard.style.display = "none";
        tabControl.style.display = "";
      }
    });
  });

  async function fetchJSON(url) {
    const res = await fetch(url);
    if (!res.ok) {
      throw new Error("HTTP " + res.status);
    }
    return await res.json();
  }

  async function loadLast() {
    try {
      const data = await fetchJSON("/api/last");
      const t = data.temp_invernadero_C;
      document.getElementById("tempValue").textContent = (t !== null && t !== undefined) ? t.toFixed(1) : "--.-";
      document.getElementById("pillEstacion").textContent = "Estación: " + (data.estacion || "--");
      document.getElementById("pillModo").textContent = "Modo control: " + (data.modo_control || "--");
      document.getElementById("tempHint").textContent = "Última lectura correcta de temperatura en el sistema.";

      const ts = data.timestamp || "";
      document.getElementById("chipTime").textContent = ts || "Sin timestamp";
      document.getElementById("chipMeta").textContent = "Modo: " + (data.modo_control || "--") + " · Día: " + (data.dia_semana || "--");

      const wallOn = !!data.vent_pared_on;
      const colgOn = !!data.vent_colg_on;
      const pumpOn = !!data.pump_on;
      const pumpAuto = !!data.pump_auto_mode;

      document.getElementById("wallStateLabel").textContent = wallOn ? "ENCENDIDOS" : "APAGADOS";
      document.getElementById("colgStateLabel").textContent = colgOn ? "ENCENDIDOS" : "APAGADOS";

      document.getElementById("freqCmdLabel").textContent = (data.freq_cmd_Hz != null) ? data.freq_cmd_Hz.toFixed(1) + " Hz" : "-- Hz";
      document.getElementById("freqOutLabel").textContent = (data.vfd_freq_out_Hz != null) ? data.vfd_freq_out_Hz.toFixed(1) + " Hz" : "-- Hz";

      document.getElementById("colgRefLabel").textContent = (data.colg_ref_unidades != null) ? data.colg_ref_unidades.toFixed(1) : "--";
      document.getElementById("colgOnLabel").textContent = (data.n_colg_vent_on != null) ? data.n_colg_vent_on : "--";

      const chipWall = document.getElementById("chipWall");
      chipWall.textContent = wallOn ? "Pared: ON" : "Pared: OFF";
      chipWall.className = "chip " + (wallOn ? "chip-ok" : "chip-bad");

      const chipColg = document.getElementById("chipColg");
      chipColg.textContent = colgOn ? "Colgantes: ON" : "Colgantes: OFF";
      chipColg.className = "chip " + (colgOn ? "chip-ok" : "chip-bad");

      const pumpDot = document.getElementById("pumpDot");
      const pumpStateLabel = document.getElementById("pumpStateLabel");
      pumpDot.classList.toggle("off", !pumpOn);
      pumpStateLabel.textContent = pumpOn ? "BOMBA ENCENDIDA" : "Bomba apagada";
      document.getElementById("pumpModeLabel").textContent = pumpAuto ? "Automático" : "Manual/forzado";

      document.getElementById("summaryText").textContent =
        "Temp: " + ((t != null) ? t.toFixed(1) + " °C" : "--.- °C") +
        " · Pared: " + (wallOn ? "ON" : "OFF") +
        " · Colgantes: " + (colgOn ? "ON" : "OFF") +
        " · Bomba: " + (pumpOn ? "ON" : "OFF");
    } catch (e) {
      console.warn("No se pudo cargar /api/last:", e);
    }
  }

  async function loadControl() {
    try {
      const c = await fetchJSON("/api/control_state");
      const wallManual = !!c.wall_manual;
      const wallOn = !!c.wall_on;
      const colgManual = !!c.colg_manual;
      const colgOn = !!c.colg_on;
      const pumpManual = !!c.pump_manual;
      const pumpOn = !!c.pump_on;

      document.getElementById("ctlWallState").textContent = wallOn ? "ON" : "OFF";
      document.getElementById("ctlWallMode").textContent = "Modo: " + (wallManual ? "Manual" : "Auto");

      document.getElementById("ctlColgState").textContent = colgOn ? "ON" : "OFF";
      document.getElementById("ctlColgMode").textContent = "Modo: " + (colgManual ? "Manual" : "Auto");

      document.getElementById("ctlPumpState").textContent = pumpOn ? "ON" : "OFF";
      document.getElementById("ctlPumpMode").textContent = "Modo: " + (pumpManual ? "Manual" : "Auto");
    } catch (e) {
      console.warn("No se pudo cargar /api/control_state:", e);
    }
  }

  async function setControl(partial) {
    try {
      await fetch("/api/control_state", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(partial)
      });
      await loadControl();
    } catch (e) {
      console.error("Error al actualizar control:", e);
    }
  }

  // Polling suave
  loadLast();
  loadControl();
  setInterval(loadLast, 5000);
  setInterval(loadControl, 7000);
</script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def root():
    return HTML_TEMPLATE
