# Asistente conversacional para entornos MongoDB

TFM — Máster de Formación Permanente en Deep Learning, Universidad Politécnica de Madrid (2025/26)

**Autor:** Lucas Silva Pérez  
**Director:** Alejandro Martín

## Descripción

Chatbot que permite a analistas de datos formular preguntas en lenguaje natural (español o inglés) y obtiene automáticamente la consulta MongoDB (MQL) correspondiente, la ejecuta y devuelve los resultados de forma comprensible, sin que el analista necesite conocer MQL.

## Arquitectura

```
Usuario (lenguaje natural)
        │
        ▼
┌─────────────────────┐
│  Interfaz web       │  Flask / FastAPI
└─────────────────────┘
        │
        ▼
┌─────────────────────┐
│  Módulo NL →  MQL   │  LLM + few-shot prompting + esquema de colección
└─────────────────────┘
        │
        ▼
┌─────────────────────┐
│  MongoDB            │  Ejecución de la query generada
└─────────────────────┘
```

## Instalación

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # Añadir claves de API y URI de MongoDB
```

## Uso

```bash
python src/web/app.py
```

## Estructura del proyecto

```
src/
  core/          # Lógica principal: conector MongoDB, generador MQL, módulo NL
  web/           # Interfaz web (rutas, templates)
  prompts/       # Plantillas de few-shot prompting por colección
data/
  schemas/       # Esquemas de colecciones MongoDB
  benchmark/     # Pares (pregunta NL, MQL esperado) para evaluación
tests/
```
