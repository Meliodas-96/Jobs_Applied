#!/usr/bin/env python3
"""
scrapers.indeed -- relee la pagina "Mis empleos > Solicitados" de Indeed.

Es el scraper que YA funcionaba (antes indeed_cdp.py). La logica no ha
cambiado: solo se han movido las utilidades CDP a scrapers/base.py.

Interfaz comun: PLATFORM, ARCHIVO, KEY, URL y scrape() -> (registros, info).
"""

import json
import re
import time
from datetime import datetime

from . import base
from .base import CDPError

PLATFORM = "indeed"
ARCHIVO = "indeed_apps.json"
KEY = "jk"
URL = "https://myjobs.indeed.com/applied"
HOST = "indeed.com"


# --- JavaScript -------------------------------------------------------------

_READY_JS = r"""(() => document.querySelectorAll('a[href*="viewjob?jk="]').length)()"""

_SCRAPE_JS = r"""
(() => {
  const out = {};
  document.querySelectorAll('a[href*="viewjob?jk="]').forEach(a => {
    const m = (a.getAttribute('href') || '').match(/jk=([a-z0-9]+)/i);
    if (!m) return;
    const jk = m[1];
    if (out[jk]) return;
    let box = a;
    for (let i = 0; i < 12 && box; i++) {
      if (box.tagName === 'LI') {
        const n = (box.innerText || '').split('\n').filter(Boolean).length;
        if (n >= 3) break;
      }
      box = box.parentElement;
    }
    const lines = box ? (box.innerText || '').split('\n').map(s => s.trim()).filter(Boolean) : [];
    out[jk] = {
      jk: jk,
      title: (a.innerText || '').split('\n')[0].trim(),
      lines: lines.slice(0, 10)
    };
  });
  return JSON.stringify({
    n: Object.keys(out).length,
    items: Object.values(out),
    url: location.href,
    title: document.title
  });
})()
"""


# --- parseo de tarjetas -----------------------------------------------------

_MESES = {
    "ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6,
    "jul": 7, "ago": 8, "sep": 9, "set": 9, "oct": 10, "nov": 11, "dic": 12,
}

_STATUS_RE = re.compile(
    r"^(solicitud\s+(enviada|vista)|la empresa no te ha seleccionado|"
    r"entrevista\b.*|rechazad\w*|no seleccionad\w*|bloquead\w*|dudos\w*)$",
    re.I,
)


def _parse_fecha(txt, hoy):
    if not txt:
        return None
    low = txt.lower()
    if "hoy" in low or "today" in low:
        return hoy.strftime("%Y-%m-%d")
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", txt)
    if m:
        return m.group(0)
    m = re.search(r"\b(\d{1,2})\s+de\s+([a-z]+)", low)
    if m:
        d = int(m.group(1))
        mon = _MESES.get(m.group(2)[:3])
        if mon and 1 <= d <= 31:
            return "%04d-%02d-%02d" % (hoy.year, mon, d)
    m = re.search(r"\b(\d{1,2})\s+([a-z]{3,4})", low)
    if m:
        d = int(m.group(1))
        mon = _MESES.get(m.group(2)[:3])
        if mon and 1 <= d <= 31:
            return "%04d-%02d-%02d" % (hoy.year, mon, d)
    return None


def _parse_card(card):
    lines = [str(x) for x in (card.get("lines") or [])]
    puesto = card.get("title") or (lines[1] if len(lines) > 1 else None)

    estado_raw = None
    for ln in lines:
        if _STATUS_RE.match(ln):
            estado_raw = ln
            break

    empresa = ubicacion = None
    for i, ln in enumerate(lines):
        if "la descripci" in ln.lower() and "empleo" in ln.lower():
            if i + 1 < len(lines):
                empresa = lines[i + 1]
            if i + 2 < len(lines):
                ubicacion = lines[i + 2]
            break
    if empresa is None and len(lines) > 3:
        empresa = lines[3]
    if ubicacion is None and len(lines) > 4:
        ubicacion = lines[4]

    fecha_raw = None
    for ln in lines:
        if "solicitado" in ln.lower() and "indeed" in ln.lower():
            fecha_raw = ln
            break
    if fecha_raw is None:
        for ln in lines:
            if "solicitado" in ln.lower():
                fecha_raw = ln
                break

    return {
        "jk": card.get("jk"),
        "puesto": puesto,
        "empresa": empresa,
        "ubicacion": ubicacion,
        "estado_raw": estado_raw,
        "fecha_raw": fecha_raw,
    }


# --- API publica ------------------------------------------------------------

def scrape(timeout=150, intentos=2):
    """Relee Indeed. Devuelve (registros, info). Lanza CDPError si no puede."""
    tab = base.open_tab(URL, HOST)
    ws_url = tab.get("webSocketDebuggerUrl")
    if not ws_url:
        raise CDPError("La pestaña de Indeed no expone websocket de depuracion")

    ws, cdp = base.connect(ws_url)
    try:
        for m in ("Page.enable", "Runtime.enable"):
            try:
                cdp.call(m, timeout=15)
            except CDPError:
                pass

        cur = None
        try:
            cur = cdp.eval("location.href", timeout=15)
        except CDPError:
            cur = None
        if not cur or "myjobs.indeed.com/applied" not in cur:
            cdp.call("Page.navigate", {"url": URL}, timeout=30)

        hoy = datetime.now()
        last = {"n": 0, "items": [], "url": None, "title": None}
        for _ in range(max(1, intentos)):
            deadline = time.time() + timeout
            ready = 0
            while time.time() < deadline:
                try:
                    ready = int(cdp.eval(_READY_JS, timeout=20) or 0)
                except CDPError:
                    ready = 0
                if ready > 0:
                    break
                time.sleep(2)
            if not ready:
                continue
            base.scroll_full_page(cdp)
            raw = cdp.eval(_SCRAPE_JS, timeout=90)
            if not raw:
                continue
            data = json.loads(raw)
            last = data
            if data.get("n"):
                break
            time.sleep(3)

        items = last.get("items") or []
        if not items:
            raise CDPError(
                "Indeed no devolvio ninguna solicitud (¿sesion caducada o "
                "verificacion de Cloudflare en la pestaña?)"
            )

        recs = []
        for c in items:
            r = _parse_card(c)
            if r.get("jk"):
                r["fecha"] = _parse_fecha(r.get("fecha_raw"), hoy)
                recs.append(r)
        info = {"url": last.get("url"), "titulo": last.get("title"), "n": len(recs)}
        return recs, info
    finally:
        try:
            ws.close()
        except Exception:
            pass


if __name__ == "__main__":
    recs, info = scrape()
    print("url  :", info.get("url"))
    print("n    :", len(recs))
    for r in recs[:5]:
        print(" -", r["jk"], "|", r.get("estado_raw"), "|", r.get("puesto"),
              "|", r.get("empresa"), "|", r.get("fecha"))