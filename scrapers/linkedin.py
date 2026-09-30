#!/usr/bin/env python3
"""
scrapers.linkedin -- PENDIENTE de implementar.

LinkedIn tiene login y anti-bot propios (y capa bastante el scraping). Hay
que probarlo con el Brave real del usuario y la sesion iniciada, igual que
Indeed. Hasta que exista un scrape() de verdad, esta plataforma NO la
refresca el boton: el panel sigue leyendo lo que haya en su JSON.

Interfaz que debe cumplir cuando se implemente:
    scrape(timeout=150, intentos=2) -> (lista_de_registros, info_dict)
con registros que traigan al menos: url, puesto, empresa, ubicacion, estado.
"""

PLATFORM = "linkedin"
ARCHIVO = "linkedin/linkedin_apps.json"
KEY = "url"
URL = "https://www.linkedin.com/my-items/saved-jobs/"


def scrape(timeout=150, intentos=2):
    raise NotImplementedError(
        "El scraper de LinkedIn todavia no esta implementado. "
        "Deja un linkedin_apps.json en linkedin/ y el panel lo leera igual."
    )