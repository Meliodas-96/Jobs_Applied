#!/usr/bin/env python3
"""
Jobs-Applied · dashboard server

Sirve la carpeta y expone /api/data, que escanea automaticamente todos los
*.json de la carpeta, los normaliza a un esquema comun y los devuelve
unificados. Pensado para ir soltando JSONs de nuevas plataformas (linkedin,
infojobs, ...) sin tocar nada: el dashboard los detecta solo.

Solo stdlib. Arranque:
    python3 server.py            # http://localhost:8899
    PORT=9001 python3 server.py
"""

import json
import os
import re
import sys
import glob
import mimetypes
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, unquote

BASE = os.path.dirname(os.path.abspath(__file__))
PORT = int(os.environ.get("PORT", "8899"))
HOST = os.environ.get("HOST", "localhost")      # bind (localhost = solo esta máquina)
DISPLAY_HOST = os.environ.get("DISPLAY_HOST", "localhost")  # lo que se muestra

EXCLUDE_NAMES = {
    "package.json", "package-lock.json", "tsconfig.json",
    "composer.json", "manifest.json",
}

# Ficheros de ejemplo: se sirven y se pueden abrir, pero NUNCA cuentan como
# datos reales en el panel. Regla exacta y predecible: el nombre acaba en
# ".example.json" (p. ej. indeed_apps.example.json). Asi no se confunde con
# un fichero real que lleve "demo" o "sample" en medio del nombre.
EXCLUDE_SUFFIX = ".example.json"

# ---------------------------------------------------------------------------
# Normalizacion
# ---------------------------------------------------------------------------

FIELD_ALIASES = {
    "id":         ["id", "num", "numero", "número", "index", "n"],
    "jk":         ["jk", "job_key", "jobkey", "id_oferta", "offer_id", "jobid", "job_id", "jobid"],
    "puesto":     ["puesto", "title", "cargo", "role", "position", "job_title", "jobtitle", "puesto_titulo", "titulo"],
    "empresa":    ["empresa", "company", "employer", "organizacion", "organización", "company_name", "compania"],
    "ubicacion":  ["ubicacion", "ubicación", "location", "lugar", "city", "ciudad", "place", "localidad"],
    "estado":     ["estado", "status", "state", "resultado", "outcome", "situacion"],
    "fecha":      ["fecha_hora", "fecha", "date", "applied_at", "applied", "timestamp", "fecha_solicitud", "created_at", "sent_at"],
    "url":        ["url", "link", "job_url", "href", "enlace", "oferta_url"],
    "salario":    ["salario_declarado", "salario_oferta", "salario", "salary", "pay", "sueldo", "compensation", "rango_salarial"],
    "idioma":     ["idioma_oferta", "idioma_respuesta", "idioma", "language", "lang"],
    "plataforma": ["plataforma", "platform", "source", "fuente", "portal"],
    "modalidad":  ["modalidad", "modality", "workplace", "work_type", "remoto", "remote"],
    "notas":      ["notas", "notes", "observaciones", "comentarios", "incidencias"],
    "cv":         ["cv_usado", "cv", "resume", "curriculum"],
}

MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}

ESTADO_RULES = [
    (r"no te ha seleccionado|no seleccionad|rechaz|reject|denegad|descartad", "Rechazada"),
    (r"entrevista|interview", "Entrevista"),
    (r"bloquead|blocked|captcha|turnstile", "Bloqueada"),
    (r"dudos|doubt|incierta", "Dudosa"),
    (r"vista|\bview\b|viewed|abierta|seen|revisad", "Vista"),
    (r"enviad|sent|applied|confirmad|confirmed|solicitud enviada", "Enviada"),
]


def _contar_estados(recs):
    out = {}
    for r in recs:
        e = r.get("estado") or "Sin estado"
        out[e] = out.get(e, 0) + 1
    return out


def plataforma_from_filename(fn):
    base = os.path.splitext(os.path.basename(fn))[0].lower()
    base = re.sub(r"[_\-\s]*(apps?|applications?|solicitudes|jobs?|data|registro|log)$", "", base)
    base = base.strip("_- ")
    return base or "desconocida"


def norm_estado(raw):
    if raw is None:
        return "Sin estado"
    s = str(raw).strip()
    if not s:
        return "Sin estado"
    low = s.lower()
    for patron, canon in ESTADO_RULES:
        if re.search(patron, low):
            return canon
    return s[:1].upper() + s[1:]


def parse_fecha(v, hoy=None):
    """Devuelve (iso_date|None, texto_original)."""
    if v is None:
        return None, None
    s = str(v).strip()
    if not s:
        return None, None
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return "%s-%s-%s" % (m.group(1), m.group(2), m.group(3)), s
    m = re.search(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})\b", s)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if y < 100:
            y += 2000
        if 1 <= mo <= 12 and 1 <= d <= 31:
            return "%04d-%02d-%02d" % (y, mo, d), s
    low = s.lower()
    y = None
    my = re.search(r"\b(20\d{2})\b", low)
    if my:
        y = int(my.group(1))
    for nombre, num in MESES.items():
        if nombre in low:
            md = re.search(r"\b(\d{1,2})\b", low)
            if md:
                d = int(md.group(1))
                if d > 31:
                    continue
                if y is None:
                    y = (hoy or datetime.now()).year
                return "%04d-%02d-%02d" % (y, num, d), s
    if "hoy" in low or "today" in low:
        return (hoy or datetime.now()).strftime("%Y-%m-%d"), s
    return None, s


def extract_records(raw):
    """Localiza la lista de registros sea cual sea el esquema del JSON."""
    if isinstance(raw, list):
        return [x for x in raw if isinstance(x, dict)] if raw else []
    if not isinstance(raw, dict):
        return []
    preferidas = (
        "solicitudes", "applications", "records", "items", "apps",
        "jobs", "entries", "rows", "results", "data",
    )
    for k in preferidas:
        v = raw.get(k)
        if isinstance(v, list) and v and isinstance(v[0], dict):
            return [x for x in v if isinstance(x, dict)]
    mejor = []
    for k, v in raw.items():
        if isinstance(v, list) and v and all(isinstance(x, dict) for x in v):
            if len(v) > len(mejor):
                mejor = [x for x in v if isinstance(x, dict)]
    return mejor


def norm_record(rec, plataforma_default, archivo, hoy):
    low = {str(k).lower(): v for k, v in rec.items()}

    def pick(canon):
        for a in FIELD_ALIASES[canon]:
            if a in low:
                val = low[a]
                if val is None:
                    continue
                if isinstance(val, str) and not val.strip():
                    continue
                return val
        return None

    fecha_iso, fecha_raw = parse_fecha(pick("fecha"), hoy)
    estado_raw = pick("estado")

    sal = pick("salario")
    if isinstance(sal, (dict, list)):
        try:
            sal = json.dumps(sal, ensure_ascii=False)
        except Exception:
            sal = str(sal)

    plataforma = pick("plataforma") or plataforma_default

    out = {
        "id": pick("id"),
        "jk": pick("jk"),
        "puesto": pick("puesto"),
        "empresa": pick("empresa"),
        "ubicacion": pick("ubicacion"),
        "estado": norm_estado(estado_raw),
        "estado_raw": (str(estado_raw).strip() if estado_raw is not None else None),
        "fecha": fecha_iso,
        "fecha_raw": fecha_raw,
        "plataforma": str(plataforma).strip().lower() if plataforma else plataforma_default,
        "url": pick("url"),
        "salario": sal,
        "idioma": pick("idioma"),
        "modalidad": pick("modalidad"),
        "notas": pick("notas"),
        "cv": pick("cv"),
        "archivo": archivo,
    }
    return out


def load_file(path):
    """Devuelve (info_archivo, records)."""
    nombre = os.path.basename(path)
    st = os.stat(path)
    info = {
        "nombre": nombre,
        "bytes": st.st_size,
        "mtime": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds"),
        "plataforma": plataforma_from_filename(path),
        "registros": 0,
        "schema": None,
        "meta": None,
        "error": None,
    }
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except Exception as e:
        info["error"] = "JSON invalido: %s" % e
        return info, []

    if isinstance(raw, dict):
        info["schema"] = raw.get("_schema")
        meta = raw.get("meta")
        if isinstance(meta, dict):
            info["meta"] = meta
            p = meta.get("plataforma")
            if isinstance(p, str) and p.strip():
                info["plataforma"] = p.strip().lower()

    hoy = datetime.now()
    registros = extract_records(raw)
    out = []
    for r in registros:
        try:
            out.append(norm_record(r, info["plataforma"], nombre, hoy))
        except Exception as e:
            info["error"] = (info["error"] or "") + " registro omitido: %s; " % e
    info["registros"] = len(out)
    return info, out


def scan_folder():
    # recursivo: coge los *.json de la carpeta Y de cualquier subcarpeta
    patron = os.path.join(BASE, "**", "*.json")
    archivos = []
    records = []
    for path in sorted(glob.glob(patron, recursive=True)):
        nombre = os.path.basename(path)
        if nombre.startswith(EXCLUDE_PREFIX):
            continue
        # ignora ficheros dentro de subcarpetas ocultas o de trabajo
        rel = os.path.relpath(path, BASE)
        if any(part.startswith((".", "_")) for part in rel.split(os.sep)[:-1]):
            continue
        if nombre in EXCLUDE_NAMES:
            continue
        if nombre.lower().endswith(EXCLUDE_SUFFIX):
            continue
        info, recs = load_file(path)
        archivos.append(info)
        records.extend(recs)

    # indice estable para filas sin id
    for i, r in enumerate(records, 1):
        if r.get("id") in (None, ""):
            r["id"] = i

    return {
        "generado": datetime.now().isoformat(timespec="seconds"),
        "carpeta": BASE,
        "archivos": archivos,
        "total_registros": len(records),
        "records": records,
    }


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    server_version = "JobsApplied/1.0"

    def log_message(self, fmt, *args):
        sys.stderr.write("[%s] %s\n" % (self.log_date_time_string(), fmt % args))

    def _send(self, code, body, ctype, extra=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store, max-age=0")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self._send(code, body, "application/json; charset=utf-8")

    def _refresh_platform(self, name):
        """
        Relee una plataforma con su scraper (scrapers/<name>.py) y regenera su
        JSON. Devuelve siempre un dict: {plataforma, ok, n?, error?}.

        Si la plataforma no tiene scraper implementado, no es un fallo grave:
        se devuelve ok=False con el motivo y el panel sigue leyendo el JSON
        que ya hubiera.
        """
        import scrapers

        spec = scrapers.get(name)
        if not spec:
            return {"plataforma": name, "ok": False,
                    "error": "plataforma desconocida"}
        if not spec.get("scrape"):
            return {"plataforma": name, "ok": False,
                    "error": spec.get("error") or "sin scraper"}

        try:
            recs, info = spec["scrape"]()
        except NotImplementedError as e:
            return {"plataforma": name, "ok": False, "error": str(e)[:400]}
        except Exception as e:
            return {"plataforma": name, "ok": False, "error": str(e)[:400]}

        key = spec["key"]
        path = os.path.join(BASE, spec["archivo"])

        # --- fusionar con el JSON existente: conservo campos que la web no da ---
        viejo = {}
        meta_prev = {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                prev = json.load(f)
            meta_prev = prev.get("meta") or {}
            for r in (prev.get("solicitudes") or prev.get("records") or []):
                k = r.get(key)
                if k:
                    viejo[k] = r
        except Exception:
            pass

        hoy = datetime.now()
        salida = []
        for i, r in enumerate(recs, 1):
            k = r.get(key)
            prev = viejo.get(k, {})
            # fusion: lo nuevo manda; lo que no trae, se conserva del anterior
            merged = dict(prev)
            merged.update({kk: vv for kk, vv in r.items() if vv not in (None, "")})
            merged["id"] = i
            merged["plataforma"] = name
            merged["estado"] = norm_estado(r.get("estado") or r.get("estado_raw"))
            merged["fecha"] = merged.get("fecha") or r.get("fecha")
            merged.pop("estado_raw", None)
            merged.pop("fecha_raw", None)
            salida.append(merged)

        doc = {
            "_schema": "%s_apps.v3" % name,
            "_descripcion": "Solicitudes de %s. Regenerado por el boton "
                            "Recargar del panel (%s via CDP)." % (name, name),
            "meta": {
                "usuario": meta_prev.get("usuario") or os.environ.get("USER_NAME", "usuario"),
                "plataforma": name,
                "cuenta_url_aplicados": spec.get("url"),
                "ultima_lectura": hoy.isoformat(timespec="seconds"),
                "total_aplicados": len(salida),
                "desglose_estado": _contar_estados(salida),
                "nota": "Regenerado por el panel (boton Recargar) via CDP sobre "
                        "el Brave del usuario. Los campos que la web no expone "
                        "(salario, hora exacta) se conservan del JSON anterior.",
            },
            "solicitudes": salida,
        }

        os.makedirs(os.path.dirname(path) or BASE, exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)

        return {
            "plataforma": name,
            "ok": True,
            "n": len(salida),
            "desglose": doc["meta"]["desglose_estado"],
            "archivo": spec["archivo"],
            "url": info.get("url") if isinstance(info, dict) else None,
        }

    def _refresh_all(self):
        """Recorre TODAS las plataformas registradas en scrapers/."""
        import scrapers

        res = {}
        for name in scrapers.names():
            res[name] = self._refresh_platform(name)
        ok = [n for n, r in res.items() if r.get("ok")]
        return {
            "ok": bool(ok),
            "actualizadas": ok,
            "plataformas": res,
            "n": sum(r.get("n") or 0 for r in res.values()),
        }

    def do_POST(self):
        p = unquote(urlparse(self.path).path)

        if p in ("/api/refresh", "/api/refresh/"):
            try:
                self._json(self._refresh_all())
            except Exception as e:
                self._json({"ok": False, "error": str(e)[:400]}, 500)
            return

        self._json({"error": "not found"}, 404)

    def do_GET(self):
        p = unquote(urlparse(self.path).path)

        if p in ("/api/data", "/api/data/"):
            try:
                self._json(scan_folder())
            except Exception as e:
                self._json({"error": str(e)}, 500)
            return

        if p in ("/api/health", "/api/health/"):
            self._json({"ok": True, "carpeta": BASE})
            return

        if p == "/":
            p = "/index.html"

        rel = p.lstrip("/")
        target = os.path.realpath(os.path.join(BASE, rel))
        if not target.startswith(os.path.realpath(BASE) + os.sep) and target != os.path.realpath(BASE):
            self._send(403, b"forbidden", "text/plain; charset=utf-8")
            return

        if os.path.isdir(target):
            target = os.path.join(target, "index.html")
        if not os.path.isfile(target):
            self._send(404, b"not found", "text/plain; charset=utf-8")
            return

        ctype = mimetypes.guess_type(target)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript", "application/json"):
            ctype += "; charset=utf-8"
        try:
            with open(target, "rb") as f:
                body = f.read()
        except OSError as e:
            self._send(500, str(e).encode(), "text/plain; charset=utf-8")
            return
        self._send(200, body, ctype)


EXCLUDE_PREFIX = ("_", ".")


def main():
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    url = "http://%s:%d" % (DISPLAY_HOST, PORT)
    print("Jobs-Applied dashboard")
    print("  carpeta : %s" % BASE)
    print("  url     : %s" % url)
    print("  parar   : Ctrl+C")
    # Abre el panel en el navegador por defecto (desactivable: OPEN_BROWSER=0)
    if os.environ.get("OPEN_BROWSER", "1") not in ("0", "false", "no"):
        try:
            webbrowser.open(url)
        except Exception as e:
            print("  aviso   : no pude abrir el navegador (%s)" % e)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nparando...")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()