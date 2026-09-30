#!/usr/bin/env python3
"""
scrapers.base -- utilidades CDP compartidas por todos los scrapers.

Nada de esto abre un navegador propio: hablamos con el Brave real del
usuario por el puerto de depuracion (CDP) en http://localhost:9222.

Requisito: websocket-client  ->  python3 -m pip install --user websocket-client
(la importacion de websocket se hace al llamar a scrape(), no aqui)
"""

import json
import os
import time
import urllib.parse
import urllib.request

CDP_HTTP = os.environ.get("CDP_HTTP", "http://localhost:9222")


class CDPError(RuntimeError):
    """Cualquier fallo hablando con el navegador por CDP."""


# --- descubrimiento de pestañas (HTTP /json) --------------------------------

def http_json(url, method="GET", timeout=6):
    req = urllib.request.Request(url, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def list_targets():
    try:
        return http_json(CDP_HTTP + "/json/list")
    except Exception as e:
        raise CDPError(
            "No puedo hablar con el navegador en %s (¿esta abierto con "
            "--remote-debugging-port=9222?): %s" % (CDP_HTTP, e)
        )


def find_tab(host_substring):
    """Primera pestaña de tipo page cuya URL contenga host_substring."""
    for t in list_targets():
        if t.get("type") == "page" and host_substring in (t.get("url") or ""):
            return t
    return None


def open_tab(url, host_substring):
    """Reutiliza la pestaña de esa plataforma o abre una nueva."""
    t = find_tab(host_substring)
    if t:
        return t
    err = None
    for method in ("PUT", "GET"):
        try:
            return http_json(
                CDP_HTTP + "/json/new?url=" + urllib.parse.quote(url, safe=""),
                method=method,
            )
        except Exception as e:
            err = e
    raise CDPError("No pude abrir una pestaña de %s: %s" % (host_substring, err))


# --- cliente CDP minimo -----------------------------------------------------

class Session:
    """Envoltorio minimo sobre el websocket de depuracion."""

    def __init__(self, ws):
        self.ws = ws
        self._id = 0

    def call(self, method, params=None, timeout=60):
        self._id += 1
        mid = self._id
        self.ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
        deadline = time.time() + timeout
        while time.time() < deadline:
            self.ws.settimeout(max(1.0, deadline - time.time()))
            try:
                msg = json.loads(self.ws.recv())
            except Exception:
                continue
            if not isinstance(msg, dict):
                continue
            if msg.get("id") == mid:
                if "error" in msg:
                    raise CDPError("%s -> %s" % (method, msg["error"]))
                return msg.get("result", {})
        raise CDPError("Timeout esperando respuesta de %s" % method)

    def eval(self, expr, timeout=60, await_promise=False):
        res = self.call("Runtime.evaluate", {
            "expression": expr,
            "returnByValue": True,
            "awaitPromise": bool(await_promise),
            "userGesture": True,
        }, timeout=timeout)
        if res.get("exceptionDetails"):
            raise CDPError(str(res["exceptionDetails"])[:300])
        return (res.get("result") or {}).get("value")


def connect(ws_url, timeout=30):
    """
    Abre un websocket CDP y devuelve una Session lista para usar.
    Importa websocket-client aqui dentro para que el modulo se pueda
    importar aunque la libreria no este instalada.
    """
    try:
        import websocket  # websocket-client
    except ImportError:
        raise CDPError(
            "Falta la libreria websocket-client. Instalala con: "
            "python3 -m pip install --user websocket-client"
        )
    ws = websocket.create_connection(ws_url, timeout=timeout, suppress_origin=True)
    return ws, Session(ws)


def scroll_full_page(session, step=700, pause=0.45, max_y=20000):
    """
    Scroll dirigido desde Python (no con promesas dentro de la pagina:
    las pestañas en segundo plano estrangulan setTimeout).
    """
    try:
        total = session.eval(
            "Math.max(document.body.scrollHeight,"
            " document.documentElement.scrollHeight)", timeout=20) or 0
    except CDPError:
        total = 0
    try:
        total = int(total)
    except Exception:
        total = 0
    y = 0
    while y < min(total, max_y):
        try:
            session.eval("window.scrollTo(0, %d)" % y, timeout=15)
        except CDPError:
            pass
        y += step
        time.sleep(pause)
    try:
        session.eval("window.scrollTo(0, 0)", timeout=15)
    except CDPError:
        pass
    time.sleep(1.5)