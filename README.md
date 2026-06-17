<p align="center">
  <img src="images/MongoMind_logo.png" alt="MongoMind logo" width="360"/>
  &nbsp;&nbsp;&nbsp;&nbsp;
</p>

# MongoMind — Asistente de Inteligencia NoSQL

TFM — Máster de Formación Permanente en Deep Learning, Universidad Politécnica de Madrid (2025/26)

**Autor:** Lucas Silva Pérez &nbsp;·&nbsp; **Director:** Alejandro Martín

---

## ¿Qué es MongoMind?

MongoMind es un asistente conversacional que permite a analistas de datos consultar bases de datos MongoDB en lenguaje natural, sin escribir una sola línea de MQL. El usuario formula su pregunta en español o inglés; MongoMind la traduce automáticamente a una query MongoDB, la ejecuta y devuelve los resultados de forma comprensible.

El sistema está diseñado para eliminar la dependencia de perfiles técnicos en el ciclo de análisis de datos: cualquier analista puede obtener respuestas de una base de datos NoSQL compleja con la misma naturalidad con la que haría una pregunta.

## ¿Por qué MongoDB Atlas?

<p align="center">
  <img src="images/mongoDB_logo.png" alt="MongoDB logo" width="280"/>
</p>

MongoDB Atlas es el servicio cloud oficial de MongoDB. Se usa en este proyecto por tres razones concretas:

- **Dataset de referencia listo para usar** — Atlas ofrece `sample_mflix`, un dataset público de películas con relaciones entre colecciones (`movies`, `comments`, `users`), ideal para cubrir todos los tipos de query que queremos evaluar.
- **Sin infraestructura local** — el tier gratuito (M0) permite desarrollar y evaluar el sistema sin gestionar instancias propias, lo que reduce la fricción durante el desarrollo del TFM.
- **Entorno realista** — las restricciones de red, autenticación y TLS de Atlas simulan las condiciones de un despliegue real, lo que hace que el sistema sea directamente transferible a producción.

## Arquitectura

```
Pregunta en lenguaje natural
        │
        ▼
   src/core/nlp.py           →  detecta la colección objetivo
        │
        ▼
   src/core/mql_generator.py →  LLM + few-shot prompting → MQL
        │
        ▼
   src/core/db_connector.py  →  ejecuta la query en MongoDB Atlas
        │
        ▼
   src/web/app.py            →  devuelve resultados + MQL generado
```

## Stack

| Capa | Tecnología |
|---|---|
| Modelo NL→MQL | Ollama + `llama3.2` (local, sin API key) |
| Base de datos | MongoDB Atlas (`sample_mflix` · `sample_airbnb` · `sample_analytics`) |
| Backend | FastAPI + Uvicorn |
| Despliegue | Docker + Docker Compose |
| Evaluación | Benchmark de 65 pares + corrección funcional (`tests/eval.py`) |

## Instalación

```bash
conda create -n tfm python=3.11
conda activate tfm
pip install -r requirements.txt
cp .env.example .env   # añadir MONGODB_URI
```

> Requiere [Ollama](https://ollama.com) instalado y ejecutándose en `localhost:11434`. Descarga el modelo con `ollama pull llama3.2`.

## Uso

Una vez hecha la instalación, sigue estos pasos para usar la herramienta.

**1. Arranca Ollama y descarga el modelo** (el LLM corre en local, sin API key):

```bash
ollama serve            # deja el servidor escuchando en localhost:11434
ollama pull llama3.2
```

**2. Prepara MongoDB Atlas** (gratis, tier M0):

- Crea un cluster M0 en [Atlas](https://www.mongodb.com/atlas).
- En el cluster, *Load Sample Dataset* (crea `sample_mflix` y el resto de `sample_*`).
- Crea un usuario de base de datos de **solo lectura** (rol `readAnyDatabase`) —
  es un requisito de seguridad: la herramienta nunca escribe en la base.
- Añade tu IP en *Network Access*.
- Copia la cadena de conexión en *Connect → Drivers*.

**3. Configura el `.env`** con tu cadena de conexión:

```bash
MONGODB_URI=mongodb+srv://USUARIO:PASSWORD@CLUSTER.mongodb.net/?retryWrites=true&w=majority
MONGODB_DB_NAME=sample_mflix
OLLAMA_MODEL=llama3.2
```

**4. Lanza la aplicación:**

```bash
python src/web/app.py   # http://localhost:8000
```

**5. Haz preguntas** en lenguaje natural. En la cabecera puedes elegir el
**dataset** (`sample_mflix`, `sample_airbnb`, `sample_analytics`). La web muestra
siempre el MQL generado junto a los resultados. Algunos ejemplos:

- *Las 10 películas con mayor puntuación IMDb*
- *¿Cuál es la duración media de las películas de acción?*
- *Movies directed by Christopher Nolan*
- *Los 10 alojamientos más caros* (dataset `sample_airbnb`)

> **¿Algo no responde?** Comprueba que Ollama está corriendo (`ollama serve`) y
> que el modelo está descargado (`ollama list`); que tu IP está permitida en
> Atlas; y que `MONGODB_URI`/`MONGODB_DB_NAME` del `.env` son correctos.

Verificación rápida (opcional): `pytest` ejecuta la batería de tests sin red, y
`python tests/demo.py` lanza 10 preguntas de extremo a extremo (necesita Ollama + Atlas).

## Datasets adicionales (multi-dataset)

`sample_mflix` ya cubre la evaluación principal. Para probar la generalización a
otras bases de datos, MongoMind soporta también `sample_airbnb` y
`sample_analytics`. Hay dos formas de cargarlos en tu cluster:

**Opción A — UI de Atlas (oficial, carga todos los sample datasets):**
Cluster → `...` → *Load Sample Dataset*. Tarda unos minutos y crea todas las
bases `sample_*`.

**Opción B — script (solo airbnb + analytics):**
Requiere un usuario de MongoDB con permisos de **escritura** (el usuario de
producción es de solo lectura). Define su `MONGODB_URI` en el entorno y ejecuta:

```bash
python scripts/load_sample_datasets.py            # clona el mirror y carga ambos
python scripts/load_sample_datasets.py --drop     # recrea las colecciones
```

El script clona automáticamente un mirror público de los datos (NDJSON) e
inserta vía PyMongo. Tras cargar, vuelve a dejar la conexión en solo lectura.

Verifica la carga (la demo incluye preguntas sobre airbnb y analytics):

```bash
python tests/demo.py   # requiere Ollama + Atlas
```

## Docker

La app se empaqueta en un contenedor que se conecta a tu **MongoDB Atlas** (vía
`MONGODB_URI`) y al **Ollama del host** (vía `host.docker.internal`). No se levanta
un MongoDB local: los datos viven en Atlas.

```bash
cp .env.example .env       # rellena MONGODB_URI (Atlas)
docker compose up --build  # http://localhost:8000
```

Requisitos: Docker Desktop, Ollama corriendo en el host (`ollama serve` + `ollama pull llama3.2`)
y un `.env` con la `MONGODB_URI` de Atlas. El compose fija `OLLAMA_HOST` automáticamente.

## Estructura

```
src/
  core/        # db_connector · mql_generator · nlp · schema_inferrer · datasets
  web/         # FastAPI app + templates HTML
  prompts/     # plantillas few-shot por colección (movies.txt, …)
data/
  schemas/     # esquemas JSON de colecciones (movies.json, …)
  benchmark/   # pares (pregunta NL, MQL esperado) para evaluación
scripts/       # utilidades (load_sample_datasets.py)
tests/
```

## Evaluación

El benchmark (`data/benchmark/movies_benchmark.json`) tiene **65 pares** (pregunta NL,
MQL de referencia) sobre `movies`, con split **70/30 dev/test**. La métrica es la
**corrección funcional** (se ejecutan ambas queries y se comparan los resultados, no el
texto), tolerante a proyección, orden y nombres de campo.

```bash
python tests/eval.py --split test --model llama3.2   # evalúa y exporta JSON
python tests/compare_results.py --split test         # tabla comparativa de modelos
```

**Comparativa de modelos** (split test, n=19, solo Ollama):

| Modelo | Funcional | Exact match | Tasa error | Latencia |
|---|---|---|---|---|
| llama3.1 (8B) | 68.4% | 52.6% | 0.0% | 4.37s |
| llama3.2 (3B) | 73.7% | 15.8% | 10.5% | 1.27s |

> La mejora de few-shots del análisis de errores (sobre el split **dev**) elevó a `llama3.2`
> de 63.2% → **73.7%** funcional en el split test (holdout), confirmando que generaliza.

## Tests

```bash
# Batería unitaria completa (sin Ollama ni Atlas)
pytest                                  # 150 tests

# Integración (requieren Atlas / Ollama) — se lanzan con python:
python tests/verify_benchmark.py        # 65 queries de referencia contra Atlas
python tests/demo.py                    # demo de defensa: 10 preguntas end-to-end
python tests/eval.py --split test       # evaluación funcional sobre el benchmark
```
