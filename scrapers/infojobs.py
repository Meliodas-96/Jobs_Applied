#!/usr/bin/env python3
"""
scrapers.infojobs -- PENDIENTE de implementar.

InfoJobs tiene login propio. Falta comprobar si la pagina de candidaturas
se puede leer con el Brave real del usuario por CDP. Hasta entonces el
boton no la refresca: el panel lee lo que haya en su JSON.

Interfaz que debe cumplir cuando se implemente:
    scrape(timeout=150, intentos=2) -> (lista_de_registros, info_dict)
"""

PLATFORM = "infojobs"
ARCHIVO = "infojobs/infojobs_apps.json"
KEY = "url"
URL = "https://www.infojobs.net/candidate/candidate-home.xhtml"


def scrape(timeout=150, intentos=2):
    raise NotImplementedError(
        "El scraper de InfoJobs todavia no esta implementado. "
        "Deja un infojobs_apps.json en infojobs/ y el panel lo leera igual."
    )