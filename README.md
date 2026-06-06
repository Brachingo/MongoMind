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
| Modelo NL→MQL | [Chirayu/nl2mongo](https://huggingface.co/Chirayu/nl2mongo) (CodeT5+ 220M, local) |
| Base de datos | MongoDB Atlas (sample_mflix) |
| Backend | FastAPI + Uvicorn |
| Dataset de evaluación | `data/benchmark/` |

## Instalación

```bash
conda create -n tfm python=3.11
conda activate tfm
pip install -r requirements.txt
cp .env.example .env   # añadir MONGODB_URI
```

> El modelo NL→MQL se descarga automáticamente de HuggingFace la primera vez (~400 MB, queda cacheado).

## Uso

```bash
# Interfaz web
python src/web/app.py   # http://localhost:8000

# Pipeline desde Python
python
>>> import src.core as mm
>>> mm.query("find top 5 movies with highest imdb rating")
```

## Estructura

```
src/
  core/        # db_connector · mql_generator · nlp · schema_inferrer
  web/         # FastAPI app + templates HTML
  prompts/     # plantillas few-shot por colección (movies.txt, …)
data/
  schemas/     # esquemas JSON de colecciones (movies.json, …)
  benchmark/   # pares (pregunta NL, MQL esperado) para evaluación
tests/
```

## Tests

```bash
pytest tests/test_db_connector.py tests/test_mql_generator.py -v   # 22 tests
python tests/smoke_test.py                                          # pipeline completo
```

## Estado actual

- [x] Entorno y conexión a MongoDB Atlas verificada
- [x] `db_connector.py` — find y aggregate con límite de seguridad
- [x] Esquema `movies.json` y plantilla few-shot `movies.txt` (12 ejemplos verificados)
- [x] `mql_generator.py` — generación MQL con nl2mongo (local, sin API key)
- [x] `nlp.py` — detección de colección por palabras clave
- [x] Pipeline end-to-end `nlp → mql_generator → db_connector`
- [ ] Interfaz web FastAPI
- [ ] Inferencia dinámica de esquema
- [ ] Benchmark y evaluación comparativa de modelos
