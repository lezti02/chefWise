# ChefWise

Recomendador de recetas con un modelo Content-Based (TF-IDF + similitud coseno).

```
FRONTEND (Angular 22)  ──HTTP/JSON──▶  BACKEND (FastAPI)  ──▶  src/recommender.py
                                                                   │
                                  models/*.joblib (TF-IDF)  ◀──────┤
                                  data/processed/*.csv      ◀──────┘
```

El CSV procesado es la fuente de verdad de las recetas (todavía no hay base de datos).

## Estructura

| Carpeta | Contenido |
|---|---|
| `frontend/` | Aplicación Angular (puerto 4200). |
| `backend/` | API FastAPI: `main.py` (app, CORS, errores), `routes.py`, `schemas.py` (contrato), `settings.py`. |
| `src/` | Lógica reutilizable del recomendador, sin dependencias de FastAPI. |
| `models/` | Artefactos ya entrenados. Modelo 1 (TF-IDF, el que usa el backend): `tfidf_vectorizer.joblib`, `recipe_tfidf_matrix.joblib`. Modelo 2 (embeddings, solo experimental): `recipe_embeddings.npy`, `embedding_metadata.json`, `embedding_model/` (este último no se versiona). |
| `data/processed/` | `recetas_unificadas_limpias.csv` (28 854 recetas, `recipe_id` entero único). |
| `data/evaluation/` | Conjunto de evaluación congelado (`eval_set_v1.json`) y resultados de la comparación Modelo 1 vs Modelo 2. |
| `notebooks/` | Limpieza, EDA, baseline TF-IDF (`03_recomendador_content_based.ipynb`) y comparación con embeddings (`04_recomendador_embeddings.ipynb`). |
| `tests/` | Pruebas del backend (pytest) contra el CSV y los modelos reales. |

Módulos de `src/`:

| Archivo | Responsabilidad |
|---|---|
| `config.py` | Rutas, tope de "rápido", peso de calidad. Sobrescribibles por variable de entorno. |
| `data_loader.py` | Lee el CSV una vez (`RecipeStore`), resumen/detalle de receta, calidad (rating bayesiano). |
| `models.py` | Carga los `.joblib`, calcula similitud solo para la consulta y valida que la matriz corresponde al CSV. |
| `preferences.py` | `UserPreferences` y **mapeo de los antojos** a datos reales (documentado en el módulo). |
| `filters.py` | Máscaras de dificultad, tiempo, país, exclusiones y antojos. |
| `ranking.py` | Ordena candidatos: similitud coseno + peso pequeño de calidad. |
| `recommender.py` | `Recommender.recommend(...)`: orquesta todo el flujo. |
| `text_utils.py` | Separa ingredientes y pasos del CSV sin inventar contenido. |
| `embeddings.py` | **Modelo 2** (experimental, aún no conectado al backend): embeddings con `sentence-transformers` + coseno. El nombre del modelo vive solo en `EMBEDDING_MODEL_NAME` (o `CHEFWISE_EMBEDDING_MODEL`). |
| `evaluation.py` | Métricas de ranking (Precision/Recall/Hit Rate/NDCG@K), construcción del conjunto de evaluación y bootstrap pareado. Común a ambos modelos. |

## Modelo 2: embeddings vs TF-IDF (experimento)

El backend sigue usando únicamente el Modelo 1 (TF-IDF). El Modelo 2 se desarrolla y se compara en
`notebooks/04_recomendador_embeddings.ipynb`; no está conectado al backend ni al frontend.

```bash
source .venv/bin/activate
pip install -r requirements.txt     # añade sentence-transformers (instala torch + transformers)

jupyter nbconvert --to notebook --execute --inplace notebooks/04_recomendador_embeddings.ipynb
```

* Primera ejecución: descarga el modelo de Hugging Face (requiere internet), lo guarda en
  `models/embedding_model/` y genera `models/recipe_embeddings.npy` (una sola vez; si ya existe y
  corresponde al CSV y al modelo configurado, se carga).
* Para probar otro modelo: `CHEFWISE_EMBEDDING_MODEL=<nombre-en-huggingface>` y borrar
  `models/recipe_embeddings.npy` y `models/embedding_metadata.json` (los artefactos guardan con qué
  modelo se crearon y se rechazan si no coinciden). El Modelo 1 no se modifica nunca.
* La evaluación usa `data/evaluation/eval_set_v1.json`, generado una vez con semilla fija y
  reutilizado por ambos modelos. Su definición de relevancia (mismo tipo de plato) y sus límites están
  explicados en la sección 9 del notebook.

## Cómo arrancar

Desde la raíz del proyecto.

### 1. Backend (http://localhost:8000)

```bash
python3 -m venv .venv                       # solo la primera vez
source .venv/bin/activate
pip install -r requirements.txt             # solo la primera vez

uvicorn backend.main:app --reload --reload-dir backend --reload-dir src
```

Docs interactivas: http://localhost:8000/docs. Al arrancar se carga el CSV y los
artefactos **una sola vez**; si falta un archivo o los artefactos no
corresponden al CSV, el servicio no arranca y explica el motivo.

Variables de entorno opcionales del backend:

| Variable | Default |
|---|---|
| `CHEFWISE_CORS_ORIGINS` | `http://localhost:4200,http://127.0.0.1:4200` (lista separada por comas) |
| `CHEFWISE_DATASET_PATH` | `data/processed/recetas_unificadas_limpias.csv` |
| `CHEFWISE_MODELS_DIR` | `models/` |

### 2. Frontend (http://localhost:4200)

```bash
cd frontend
npm install        # solo la primera vez
npm start          # = ng serve
```

**URL del backend:** Angular no lee archivos `.env`; usa archivos de entorno
compilados.

- `frontend/src/environments/environment.development.ts` → `apiUrl: 'http://localhost:8000'` (`npm start`).
- `frontend/src/environments/environment.ts` → `apiUrl: ''` (build de producción: mismo origen que el frontend; cámbialo si el backend vive en otro dominio y agrega ese origen a `CHEFWISE_CORS_ORIGINS`).

## Endpoints

| Método y ruta | Descripción |
|---|---|
| `GET /health` | `{"status": "ok"}` |
| `POST /recommendations` | Top-N de "Sorpréndeme" según las preferencias. |
| `POST /recommendations/by-ingredients` | Top-N de "Con lo que tengo" (similitud TF-IDF con los ingredientes escritos). |
| `GET /recipes/{recipe_id}` | Receta completa del CSV (ingredientes, pasos, metadatos). 404 si no existe. |

Errores: `404` receta inexistente · `422` request inválido · `500` mensaje seguro
(el detalle queda en el log del servidor).

### `POST /recommendations`

```json
{
  "antojos": ["rapido"],
  "difficulty": "facil",
  "max_time": 30,
  "countries": [],
  "exclude_ids": [],
  "top_n": 12
}
```

- `antojos`: `rapido | saludable | reconfortante | dulce | picante | ligero`.
- `difficulty`: `facil | intermedio | reto` (valores de `app_difficulty`).
- `max_time`: minutos; se compara con `total_time_min`.
- `countries`: valores de `country`; vacío = cualquiera.
- `exclude_ids`: `recipe_id` que no deben aparecer (ocultas, ya cocinadas, ya mostradas).

Respuesta: `{"recommendations": [...], "meta": {...}}`. Cada elemento trae
`recipe_id, name, ingredients[], difficulty, total_time_min, servings, country,
category, meal_type, rating, rating_votes, source, source_url, similarity, score`.
Un dato que el CSV no tiene llega como `null` (el dataset **no tiene imágenes**,
por eso no hay `image_url`).

### Cómo se interpretan los controles de Sorpréndeme

1. **Filtros que siempre se respetan:** dificultad exacta (`app_difficulty`), tiempo
   (`total_time_min <= max_time`; si se pide tiempo o dificultad, las recetas sin ese
   dato se descartan), país y `exclude_ids`.
2. **Antojos** (ver `src/preferences.py`): "rápido" = tope de 30 min; "dulce" =
   `app_category == 'postre'`; "saludable" / "ligero" = etiquetas reales
   (`category_tags`, `diet_tags`, `meal_type`) + palabras en el nombre; "picante" =
   chile/jalapeño/habanero… en nombre o ingredientes; "reconfortante" = platos tipo
   sopa, guiso, caldo, horneados en el nombre. Con varios antojos se piden todos; si
   quedan menos de `top_n` candidatos se acepta cualquiera y, en último caso, solo se
   ordena por similitud (`meta.relaxed` lo indica).
3. **Ranking:** los términos de los antojos se vectorizan con el TF-IDF **ya
   entrenado** y se calcula el coseno contra la matriz guardada (solo para esa
   consulta; no existe una matriz receta×receta). `score = similitud + 0.05 × calidad`
   (rating bayesiano).
4. **"Mostrar ideas nuevas"** con los mismos controles excluye las recetas ya
   mostradas; si cambias un control, se empieza de cero.

## Pruebas

```bash
# Backend (usa el CSV y los modelos reales) — desde la raíz, con el venv activo
python -m pytest -q

# Frontend (Vitest) — desde frontend/
cd frontend && npm test -- --watch=false
```

## Notas

- Las favoritas, guardadas, historial, alergias y recetas ocultas siguen en el
  `localStorage` del navegador (con una copia ligera de cada receta). Pasarán al
  backend cuando exista base de datos.
- El chat flotante sigue siendo una maqueta (`chat.service.ts`): el chef virtual es
  una funcionalidad futura y no genera recetas.
- Los `.joblib` se guardaron con scikit-learn 1.9.x; usa una versión compatible
  (`requirements.txt`).
