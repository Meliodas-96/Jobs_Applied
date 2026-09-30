# Jobs-Applied · Dashboard de solicitudes de empleo

Documentación completa del panel. Todo lo que hay aquí está verificado en la
máquina el 2026-09-30 (CEST). Si algo no coincide con el código, manda el código.

Directorio: `~/Documentos/Jobs-Applied/`
URL local: `http://localhost:8899/`

---

## 1. Qué es

Un dashboard en modo oscuro que lee TODOS los JSON de esta carpeta (y de sus
subcarpetas), los normaliza a un esquema común y los muestra unificados:
KPIs, gráficas y una tabla filtrable. Sirve para llevar el registro de
solicitudes de empleo enviadas en distintas plataformas (Indeed, LinkedIn,
InfoJobs, …).

Dos ideas de diseño:

1. **Los datos son ficheros JSON.** No hay base de datos. Sueltas un JSON nuevo
   y aparece solo en el panel.
2. **Cada plataforma puede tener su propio esquema.** El servidor traduce alias
   de campos (puesto/title/job_title, empresa/company/company_name, …) para que
   todo se vea igual sin tener que reformatear nada a mano.

---

## 2. Ficheros de la carpeta

```
~/Documentos/Jobs-Applied/
├── server.py             Servidor HTTP + normalizador + /api/refresh (stdlib)
├── index.html            El panel (Tailwind por CDN + Chart.js por CDN)
├── indeed_apps.json      Datos reales: 40 solicitudes de Indeed
├── scrapers/             Un módulo por plataforma de empleo
│   ├── __init__.py       Registro de plataformas + despacho
│   ├── base.py           Utilidades CDP compartidas (websocket-client)
│   ├── indeed.py         Scraper de Indeed (IMPLEMENTADO)
│   ├── linkedin.py       PENDIENTE
│   ├── infojobs.py       PENDIENTE
│   └── glassdoor.py      PENDIENTE
└── README.md             Este fichero
```

- `server.py` (471 líneas) — backend: servidor, normalizador y `POST /api/refresh`.
- `index.html` (545 líneas) — frontend.
- `scrapers/` — un fichero por plataforma con la misma interfaz
  (`PLATFORM`, `ARCHIVO`, `KEY`, `URL`, `scrape()`). El botón `Recargar` recorre
  todas las registradas. `scrapers/base.py` centraliza el cliente CDP.
- `indeed_apps.json` (esquema `indeed_apps.v3`) — datos; lo regenera el botón.

---

## 3. Arrancar / parar

Arrancar:

```bash
cd ~/Documentos/Jobs-Applied
python3 server.py
```

Salida esperada:

```
Jobs-Applied dashboard
  carpeta : ~/Documentos/Jobs-Applied
  url     : http://localhost:8899
  parar   : Ctrl+C
```

Variables de entorno opcionales:

- `PORT` — puerto (por defecto `8899`). Ej: `PORT=9001 python3 server.py`
- `HOST` — interfaz de escucha (por defecto `localhost`, solo esta máquina).
- `DISPLAY_HOST` — solo cambia el nombre que el servidor imprime en pantalla
  (por defecto `localhost`).
- `OPEN_BROWSER` — al arrancar, abre el panel en el navegador por defecto
  (por defecto `1`). Para no abrirlo: `OPEN_BROWSER=0 python3 server.py`.

Parar: `Ctrl+C`, o `pkill -f "[s]erver.py"`.

> Nota: usar el truco del corchete `[s]erver.py` en pkill/pgrep para que el
> patrón no se matche a sí mismo (si no, la shell que lanza el pkill muere).

Requiere **Python 3** (probado con 3.14.7). El panel, `/api/data` y `/api/health`
son 100% biblioteca estándar (sin `pip install`). El botón `Recargar`, que sí
relee Indeed vía CDP, usa además `websocket-client`:

```bash
python3 -m pip install --user websocket-client
```

Sin esa librería el panel funciona igual; solo el botón `Recargar` devuelve
error al intentar leer Indeed.

Acceso desde otro dispositivo de la red: arrancar con `HOST=0.0.0.0` y abrir
`http://<ip-del-equipo>:8899/`. No hay autenticación: es un panel local.

---

## 4. API HTTP

El servidor responde a:

| Ruta            | Qué devuelve                                                    |
|-----------------|-----------------------------------------------------------------|
| `/`             | `index.html` (el panel).                                        |
| `/api/data`     | JSON con todos los registros normalizados + info de ficheros.   |
| `/api/refresh`  | **POST.** Relee Indeed vía CDP y regenera `indeed_apps.json`.   |
| `/api/health`   | `{"ok": true, "carpeta": "..."}` para comprobar que está vivo.  |
| `/cualquier-x`  | Sirve el fichero correspondiente de la carpeta (bloquea `../`). |

`POST /api/refresh` es lo que dispara el botón `Recargar`. Devuelve
`{"ok": true, "n": 40, "desglose": {...}, "url": "...", "archivo": "..."}` o, si
no pudo, `{"ok": false, "error": "..."}` (p. ej. Brave sin CDP o sesión de
Indeed caducada). Tarda unos segundos: abre/conecta a la pestaña de Indeed,
hace scroll, lee las tarjetas y reescribe el JSON.

Todas las respuestas llevan `Cache-Control: no-store`, así que el navegador
nunca sirve datos viejos.

Ejemplo rápido:

```bash
curl -s http://localhost:8899/api/health
curl -s http://localhost:8899/api/data | python3 -m json.tool | head -40
```

Estructura de `/api/data`:

```json
{
  "generado": "2026-09-30T12:18:08",
  "carpeta": "/ruta/donde-lo-clones/Jobs-Applied",
  "archivos": [
    {
      "nombre": "indeed_apps.json",
      "bytes": 15452,
      "mtime": "2026-09-30T11:58:23",
      "plataforma": "indeed",
      "registros": 40,
      "schema": "indeed_apps.v3",
      "meta": { ... },          // el bloque "meta" del JSON, si lo tiene
      "error": null             // o el mensaje si el JSON es inválido
    }
  ],
  "total_registros": 40,
  "records": [
    {
      "id": 1,
      "jk": "70672bc3e6087b84",
      "puesto": "Tecnico de Sistemas Windows Linux",
      "empresa": "TECDATA ENGINEERING",
      "ubicacion": "Madrid, Madrid",
      "estado": "Enviada",
      "estado_raw": "Solicitud enviada",
      "fecha": "2026-09-30",
      "fecha_raw": "2026-09-30",
      "plataforma": "indeed",
      "url": "https://es.indeed.com/viewjob?jk=70672bc3e6087b84",
      "salario": null,
      "idioma": "es",
      "modalidad": null,
      "notas": null,
      "cv": null,
      "archivo": "indeed_apps.json"
    }
  ]
}
```

---

## 5. Detección automática de JSON

Esta es la parte clave. El servidor escanea en **cada petición** a `/api/data`:

- Patrón: `**/*.json` con `glob(..., recursive=True)` → **recursivo**.
  O sea: coge los JSON de la carpeta raíz **y** de cualquier subcarpeta.
- Ignora ficheros cuyo nombre empiece por `_` o `.` (temporales/backups).
- Ignora ficheros en subcarpetas cuyo nombre empiece por `.` o `_`
  (p. ej. `_backup/`, `.tmp/`).
- Ignora nombres concretos que no son datos: `package.json`,
  `package-lock.json`, `tsconfig.json`, `composer.json`, `manifest.json`.
- Ignora ficheros de EJEMPLO: si el nombre acaba en `.example.json`
  (p. ej. `indeed_apps.example.json`), no entra en el panel. Así puedes
  tener la plantilla para GitHub sin que sus datos falsos se mezclen con
  los reales. La regla es exacta (sufijo), no una heurística por palabras.
- Si un JSON está malformado, **no rompe nada**: ese fichero se lista con su
  campo `error` y el resto se procesa igual.

Recomendación de organización: **una carpeta por plataforma**.

```
Jobs-Applied/
├── indeed_apps.json
├── linkedin/
│   └── linkedin_apps.json
├── infojobs/
│   └── infojobs_apps.json
└── glassdoor/
    └── glassdoor_apps.json
```

Se puede mezclar raíz y subcarpetas; lo verificado es que ambas se detectan.

---

## 6. Esquema esperado de cada JSON

No es obligatorio un esquema exacto: el servidor es tolerante. Pero para que
salga todo bien, lo ideal es un objeto con:

- `meta` (opcional): metadatos del fichero.
  - `meta.plataforma` — si existe, manda sobre el nombre del fichero para
    etiquetar los registros (p. ej. `"linkedin"`).
- Una **lista de registros**. El servidor busca la lista en estas claves, por
  orden: `solicitudes`, `applications`, `records`, `items`, `apps`, `jobs`,
  `entries`, `rows`, `results`, `data`. Si no encuentra ninguna, usa la lista
  de diccionarios más larga que haya en el objeto.
- También vale que el JSON sea directamente una lista `[ {...}, {...} ]`.

### Campos por registro y sus alias aceptados

El servidor busca en cada registro el primer alias que exista (sin distinguir
mayúsculas):

| Campo canónico | Alias aceptados |
|---|---|
| `id`         | `id`, `num`, `numero`, `número`, `index`, `n` |
| `jk`         | `jk`, `job_key`, `jobkey`, `id_oferta`, `offer_id`, `jobid`, `job_id` |
| `puesto`     | `puesto`, `title`, `cargo`, `role`, `position`, `job_title`, `jobtitle`, `puesto_titulo`, `titulo` |
| `empresa`    | `empresa`, `company`, `employer`, `organizacion`, `organización`, `company_name`, `compania` |
| `ubicacion`  | `ubicacion`, `ubicación`, `location`, `lugar`, `city`, `ciudad`, `place`, `localidad` |
| `estado`     | `estado`, `status`, `state`, `resultado`, `outcome`, `situacion` |
| `fecha`      | `fecha_hora`, `fecha`, `date`, `applied_at`, `applied`, `timestamp`, `fecha_solicitud`, `created_at`, `sent_at` |
| `url`        | `url`, `link`, `job_url`, `href`, `enlace`, `oferta_url` |
| `salario`    | `salario_declarado`, `salario_oferta`, `salario`, `salary`, `pay`, `sueldo`, `compensation`, `rango_salarial` |
| `idioma`     | `idioma_oferta`, `idioma_respuesta`, `idioma`, `language`, `lang` |
| `plataforma` | `plataforma`, `platform`, `source`, `fuente`, `portal` |
| `modalidad`  | `modalidad`, `modality`, `workplace`, `work_type`, `remoto`, `remote` |
| `notas`      | `notas`, `notes`, `observaciones`, `comentarios`, `incidencias` |
| `cv`         | `cv_usado`, `cv`, `resume`, `curriculum` |

Ejemplo mínimo válido (cualquiera de estos esquemas vale):

```json
{
  "meta": { "plataforma": "linkedin" },
  "records": [
    {
      "job_title": "Azure Administrator",
      "company_name": "NTT Data",
      "location": "Barcelona",
      "status": "Applied",
      "applied_at": "2026-09-28",
      "link": "https://www.linkedin.com/jobs/view/123",
      "salary": "35.000-40.000 EUR",
      "work_type": "Remoto"
    }
  ]
}
```

Ese mismo JSON, tras normalizar, sale como puesto "Azure Administrator",
empresa "NTT Data", estado "Enviada", plataforma "linkedin", modalidad "Remoto".

### Plataforma cuando no hay `meta.plataforma`

Se deduce del **nombre del fichero**: se quita la extensión y sufijos tipo
`_apps`, `_applications`, `_solicitudes`, `_jobs`, `_data`, `_registro`, `_log`.
Ejemplos:

- `indeed_apps.json`  → plataforma `indeed`
- `linkedin_apps.json` → plataforma `linkedin`
- `infojobs.json`     → plataforma `infojobs`
- `raro.json`         → plataforma `raro`
- (si queda vacío)    → `desconocida`

---

## 7. Normalización

### Estados

Cada `estado`/`status` en bruto se traduce a un estado canónico por regex
(primera regla que casa, en este orden):

| Estado canónico | Patrones que lo activan |
|---|---|
| `Rechazada`  | no te ha seleccionado, no seleccionad, rechaz, reject, denegad, descartad |
| `Entrevista` | entrevista, interview |
| `Bloqueada`  | bloquead, blocked, captcha, turnstile |
| `Dudosa`     | dudos, doubt, incierta |
| `Vista`      | vista, view, viewed, abierta, seen, revisad |
| `Enviada`    | enviad, sent, applied, confirmad, confirmed, solicitud enviada |

Si no casa ninguna regla, se deja el texto tal cual (con la primera letra en
mayúscula). Si `estado` no viene, el canónico es `Sin estado`.

Se guardan dos campos: `estado` (normalizado) y `estado_raw` (el original).

### Fechas

`fecha` intenta parsear en este orden y guarda `fecha` como ISO `YYYY-MM-DD`
(si lo consigue) y `fecha_raw` como el texto original:

1. `YYYY-MM-DD` (ISO).
2. `D/M/YYYY` o `D-M-YYYY` (y variantes con año de 2 dígitos → se asume 20xx).
3. Mes en texto + día (español o inglés), p. ej. `23 de septiembre` → año actual
   si no se indica otro.
4. `hoy` / `today` → fecha de hoy.

Si no consigue parsear, `fecha` queda `null` y `fecha_raw` conserva el texto
(esto es lo que pasa con literales como "hoy en Indeed" que no llevan fecha).

### Salario

Si el valor es un objeto o lista, se serializa a texto JSON para no perderlo.
Si es texto (p. ej. `"35.000-40.000 EUR"`), se muestra tal cual.

### Modalidad

No se normaliza: se toma el valor del campo tal cual (esperado: `Remoto`,
`Híbrido`, `Presencial`). Si no viene, queda `null` y en la tabla sale "—".

### IDs ausentes

Si un registro no trae `id`, se le asigna un índice secuencial estable
(1, 2, 3, …) al construir la respuesta. No se escribe en el fichero.

---

## 8. El panel (index.html)

Sin build, sin npm: Tailwind y Chart.js por CDN.

- Tailwind: `https://cdn.tailwindcss.com` (config en línea: tema oscuro, paleta
  `ink` y `aurora`).
- Chart.js: `https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js`.

Si no hay red, el panel carga pero sin estilos ni gráficas (la tabla y los
datos siguen funcionando).

### Secciones

1. **Cabecera fija** — nombre, ruta de la carpeta, indicador de estado
   (`listo` / `cargando…` / `actualizado` / `error: …`) y botón `Recargar`.
2. **6 KPIs**:
   - `Registros` — total de filas.
   - `Plataformas` — portales distintos.
   - `Empresas` — empresas únicas (sin contar vacías).
   - `Enviadas` — estado `Enviada`.
   - `En juego` — `Vista` + `Entrevista`.
   - `Descartadas` — `Rechazada` + `Bloqueada`.
3. **Gráficas** (Chart.js):
   - Doughnut: registros por plataforma.
   - Barras: registros por estado (color por estado).
   - Barras horizontales: top 10 empresas.
   - Línea con área: actividad por fecha (solo registros con fecha reconocida;
     el tooltip avisa cuántos quedaron sin fecha).
4. **Ficheros detectados** — lista de cada JSON con plataforma, esquema, tamaño,
   mtime y nº de registros. Si un fichero tiene error, se marca en rojo con el
   mensaje.
5. **Tabla de registros** — columnas: #, Puesto, Empresa, Ubicación, Estado
   (badge de color), Plataforma, Modalidad, Fecha, Salario, Oferta (enlace).
6. **Filtros** — caja de búsqueda libre (puesto, empresa, ubicación, jk, notas,
   salario, idioma) + desplegables de plataforma, estado y modalidad + orden
   (fecha ↓/↑, empresa A-Z, puesto A-Z) + botón `Limpiar`.

### Refresco automático

- `setInterval(..., 4*60*60*1000)` — cada **4 horas** se vuelve a pedir
  `/api/data`. El auto-refresco solo relee los ficheros locales: **NO** consulta
  Indeed.
- El botón `Recargar` sí consulta Indeed: llama a `POST /api/refresh`, relee tu
  página de solicitados vía CDP, regenera `indeed_apps.json` y recarga el panel.
- Se recalcula una "firma" (solo `archivos` + `records`, sin el campo
  `generado`, que cambia siempre) y **solo se redibuja si los datos cambiaron**.
  Así no parpadean las gráficas en cada ciclo.
- El botón `Recargar` fuerza el redibujado aunque no haya cambios.
- El campo "actualizado" sí se refresca en cada petición (muestra la hora de la
  última lectura correcta).

### Seguridad de render

Todo texto que viene de los JSON pasa por una función `esc()` que escapa
`& < > " '` antes de inyectarse en el HTML de la tabla. Es lo que evita que un
título raro rompa el panel o inyecte HTML.

---

## 9. Cómo añadir una plataforma nueva (paso a paso)

Una plataforma nueva tiene dos partes independientes: (a) que el panel LEA su
JSON, y (b) que el botón `Recargar` lo REGENERE solo.

(a) Que el panel lo lea — automático, sin tocar código:

1. Crea la carpeta si quieres orden: `mkdir linkedin`.
2. Escribe el JSON (nombre libre; el prefijo se usa como plataforma).
   Idealmente con `"meta": { "plataforma": "linkedin" }` y una lista bajo
   `records`, `solicitudes` o similar.
3. Pulsa `Recargar` en el panel para verlo al instante (el reescaneo automático
   es cada 4 h).
   - Si no lo ves: comprueba `curl .../api/data` para ver si el fichero se
     detectó y con qué error (si lo hay).

(b) Que el botón lo regenere desde la web — hay que escribir un scraper:

1. Crea `scrapers/<plataforma>.py` (ya hay plantillas `linkedin.py`,
   `infojobs.py`, `glassdoor.py` que lanzan `NotImplementedError`).
2. Cumple la interfaz: `PLATFORM`, `ARCHIVO`, `KEY`, `URL` y
   `scrape(timeout=150, intentos=2) -> (registros, info)`. Los registros deben
   traer al menos puesto, empresa, ubicacion, estado y la clave `KEY`.
3. Regístrala en `_PLATFORMS` de `scrapers/__init__.py` (nombre → archivo + key).
   A partir de ahí el botón `Recargar` la coge sola: aparece en el resumen de
   `/api/refresh` y se refresca junto a las demás.
4. Mientras no exista `scrape()`, no pasa nada: la plataforma sale en el
   resumen con `ok:false` y su motivo, y el panel sigue leyendo su JSON.

Comprobar por consola sin abrir el navegador:

```bash
curl -s http://localhost:8899/api/data \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print([f['nombre'] for f in d['archivos']], d['total_registros'])"
```

---

## 10. Datos actuales (indeed_apps.json)

- Esquema: `indeed_apps.v3` (lo regenera `POST /api/refresh` / botón `Recargar`).
- 40 solicitudes, todas de Indeed (estado de la cuenta a 2026-09-30).
- Desglose por estado: **36 Enviada · 3 Vista · 1 Rechazada**.
- Origen: leídas de `https://myjobs.indeed.com/applied` (Indeed declaraba 40).
- Campos que no se pudieron rellenar para las solicitudes ya enviadas:
  `salario` y la hora exacta (`fecha_hora`); sí hay fecha (día) en todas.
- Aviso heredado en el propio JSON: un recuento anterior de "19 confirmadas + 2
  dudosas + 1 bloqueada" era manual e incompleto; el total real fue 40.

### Campos del esquema indeed_apps.v3

```
id, jk, puesto, empresa, ubicacion, url, estado, fecha,
plataforma, idioma_oferta, modalidad
```

### Plantilla para el próximo run

Cuando se automatice la solicitud de empleo, cada entrada nueva debe registrar
TODOS estos campos en el momento del envío:

```json
{
  "id": 41,
  "fecha_hora": "2026-10-01T09:14:00+02:00",
  "plataforma": "indeed",
  "empresa": "ACME",
  "puesto": "Administrador M365",
  "ubicacion": "Barcelona (híbrido)",
  "url": "https://es.indeed.com/viewjob?jk=XXXX",
  "jk": "XXXX",
  "idioma_respuesta": "es",
  "salario_declarado": "30.000-34.000",
  "salario_oferta": "30.000-34.000",
  "estado": "Enviada",
  "cv_usado": "CV-ALI.pdf",
  "notas": ""
}
```

Regla del proyecto (ya grabada en la skill `job-application-automation`): el
log de cada solicitud se escribe en
`~/Documentos/Jobs-Applied/indeed_apps.json` (o el fichero de su plataforma),
creándolo al **principio** del run y añadiendo cada entrada según se confirma.

---

## 11. Problemas típicos

- **"La página no carga":** comprueba que el servidor corre:
  `curl -s http://localhost:8899/api/health`. Si no responde, arráncalo:
  `cd ~/Documentos/Jobs-Applied && python3 server.py`.
- **"Un JSON no aparece":** confirma que está en la carpeta o en una subcarpeta,
  que no empieza por `_`/`.`, y que es JSON válido:
  `python3 -m json.tool fichero.json > /dev/null`.
  Míralo en `/api/data` → `archivos` → campo `error`.
- **"Un campo sale como '—' aunque esté en el JSON":** ese campo usa un nombre
  que no está en la tabla de alias. Añade el alias en `FIELD_ALIASES` de
  `server.py` o renombra el campo.
- **"El estado sale raro":** el texto no casa ninguna regla; añade su patrón en
  `ESTADO_RULES` (server.py) o usa un texto que case.
- **"El puerto está ocupado":** arranca con otro `PORT=9001 python3 server.py`.
- **"Se quedó colgado tras un Ctrl+C raro":** `pkill -f "[s]erver.py"` y
  arráncalo de nuevo.
- **"El botón Recargar da error":** el panel necesita (a) el Brave abierto con
  `--remote-debugging-port=9222` y (b) sesión iniciada en Indeed. Errores
  típicos: "No puedo hablar con el navegador en http://localhost:9222" (Brave
  sin CDP) o "Indeed no devolvió ninguna solicitud" (sesión/Cloudflare).
  Compruébalo: `curl -s http://localhost:9222/json/version | head -3`.
  El host del CDP se puede cambiar con la variable `CDP_HTTP`.

---

## 12. Ideas de ampliación (no implementadas)

- Botón para cambiar el estado de una fila desde el panel (escribiría en el
  JSON de origen).
- Exportar a CSV/Excel.
- Gráficas de estados por mes.
- Un script que regenere `indeed_apps.json` releyendo Indeed cada X horas —
  **hecho a medias**: el botón `Recargar` ya relee Indeed bajo demanda; falta
  programarlo en cron para que se refresque solo.

---

_Última actualización: 2026-09-30. Ficheros al escribir esto:_
_- server.py · 471 líneas · 16 759 bytes_
_- index.html · 545 líneas · 26 085 bytes_
_- scrapers/__init__.py · base.py · indeed.py · linkedin.py · infojobs.py · glassdoor.py_
_- indeed_apps.json · ~17 KB · 40 registros (esquema v3)_