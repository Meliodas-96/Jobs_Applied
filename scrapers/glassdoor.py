#!/usr/bin/env python3
"""
scrapers.glassdoor -- PENDIENTE de implementar.

Glassdoor tiene login y Cloudflare agresivo; es el candidato mas probable a
no ser automatizable. Hasta que haya scrape() de verdad, el boton no la
refresca: el panel lee lo que haya en su JSON.

Interfaz que debe cumplir cuando se implemente:
    scrape(timeout=150, intentos=2) -> (lista_de_registros, info_dict)
"""

PLATFORM = "glassdoor"
ARCHIVO = "glassdoor/glassdoor_apps.json"
KEY = "url"
URL = "https://www.glassdoor.es/index.htm"


def scrape(timeout=150, intentos=2):
    raise NotImplementedError(
        "El scraper de Glassdoor todavia no esta implementado. "
        "Deja un glassdoor_apps.json en glassdoor/ y el panel lo leera igual."
    )