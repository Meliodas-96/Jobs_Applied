#!/usr/bin/env python3
"""
scrapers -- un modulo por plataforma de empleo.

Cada plataforma vive en su propio fichero (indeed.py, linkedin.py, ...) y
expone la MISMA interfaz:

    PLATFORM = "indeed"                  # nombre corto
    ARCHIVO  = "indeed_apps.json"        # JSON que regenera (relativo a la raiz)
    KEY      = "jk"                      # campo que identifica la oferta (para fusionar)
    URL      = "https://..."             # pagina de la que lee
    def scrape(timeout=150, intentos=2) -> (lista_de_registros, info_dict)

Anadir una plataforma = crear scrapers/<nombre>.py con esa interfaz y
registrarla aqui abajo. El servidor la coge sola: aparece en /api/refresh,
en el panel y en el escaneo de JSON sin tocar nada mas.

Todos los scrapers se enganchan al navegador REAL del usuario via CDP
(websocket) en http://localhost:9222. No abren navegador propio.
"""

import importlib

# ---------------------------------------------------------------------------
# Registro de plataformas.
#
#   nombre  -> {archivo, key}
#
# archivo: ruta (relativa a Jobs-Applied/) del JSON que regenera el scraper.
# key    : campo del registro que sirve de clave para fusionar con lo previo
#          (si el scraper devuelve un campo distinto, manda el KEY del modulo).
# ---------------------------------------------------------------------------
_PLATFORMS = {
    "indeed":   {"archivo": "indeed_apps.json",                     "key": "jk"},
    "linkedin": {"archivo": "linkedin/linkedin_apps.json",          "key": "url"},
    "infojobs": {"archivo": "infojobs/infojobs_apps.json",          "key": "url"},
    "glassdoor": {"archivo": "glassdoor/glassdoor_apps.json",       "key": "url"},
}


def names():
    """Nombres de todas las plataformas registradas."""
    return list(_PLATFORMS.keys())


def get(name):
    """
    Devuelve un dict con todo lo necesario para operar con una plataforma:

        {name, archivo, key, url, module, scrape, error?}

    module/scrape son None si el modulo no existe todavia o no se puede
    importar. Eso NO es un fallo del panel: la plataforma simplemente se
    queda con el JSON que ya haya en su carpeta.
    """
    name = (name or "").strip().lower()
    spec = _PLATFORMS.get(name)
    if not spec:
        return None

    out = {
        "name": name,
        "archivo": spec["archivo"],
        "key": spec["key"],
        "url": None,
        "module": None,
        "scrape": None,
        "error": None,
    }

    try:
        mod = importlib.import_module("scrapers." + name)
    except Exception as e:
        out["error"] = "no puedo importar scrapers.%s: %s" % (name, e)
        return out

    out["module"] = mod
    out["archivo"] = getattr(mod, "ARCHIVO", spec["archivo"])
    out["key"] = getattr(mod, "KEY", spec["key"])
    out["url"] = getattr(mod, "URL", None)
    out["scrape"] = getattr(mod, "scrape", None)
    return out