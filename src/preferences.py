"""Preferencias estructuradas y mapeo de los "antojos" de Sorpréndeme a datos reales.

MAPEO DE ANTOJOS (valores verificados contra data/processed/*.csv)
------------------------------------------------------------------
Ningún antojo existe como columna en el dataset, así que cada uno se traduce a
una combinación de:

* un tope de tiempo        -> columna `total_time_min`
* categorías/etiquetas     -> columnas `app_category`, `category_tags`,
                              `diet_tags` y `meal_type` (valores exactos, sin
                              acentos y en minúsculas)
* palabras en el texto     -> nombre e ingredientes de la receta (regex)
* términos de consulta     -> texto que se vectoriza con el TF-IDF YA entrenado
                              para ordenar por similitud coseno

Una receta "cumple" un antojo si coincide con CUALQUIERA de sus categorías,
etiquetas o palabras (OR dentro del antojo). Si el usuario elige varios
antojos se piden todos (AND); si así quedan muy pocos candidatos se acepta
cualquiera de ellos (ver `Recommender.recommend`).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .config import DEFAULT_TOP_N, QUICK_MAX_MINUTES

DIFFICULTIES = ("facil", "intermedio", "reto")  # valores de `app_difficulty`


@dataclass(frozen=True)
class MoodRule:
    key: str
    label: str
    query_terms: str
    max_minutes: int | None = None
    categories: frozenset[str] = frozenset()  # `app_category`
    tags: frozenset[str] = frozenset()  # etiquetas exactas (category_tags/diet_tags/meal_type)
    name_regex: str | None = None  # sobre el nombre normalizado
    text_regex: str | None = None  # sobre nombre + ingredientes normalizados


MOOD_RULES: dict[str, MoodRule] = {
    rule.key: rule
    for rule in (
        MoodRule(
            key="rapido",
            label="Algo rápido",
            # No hay etiqueta "rápido": se usa el tiempo total real de la receta.
            max_minutes=QUICK_MAX_MINUTES,
            query_terms="rapido rapida express",
        ),
        MoodRule(
            key="saludable",
            label="Saludable",
            categories=frozenset(),
            tags=frozenset(
                {
                    "recomendada para perder peso",
                    "saludables",
                    "alto en fibra",
                    "alto contenido de fibra",
                    "buena fuente de fibra",
                    "alto en proteinas",
                    "bajo en calorias",
                }
            ),
            name_regex=r"\b(?:ensalada|verdura|vegetal|integral|light|saludable)(?:s|es)?\b",
            query_terms="saludable ensalada verduras integral",
        ),
        MoodRule(
            key="reconfortante",
            label="Reconfortante",
            # Sin etiqueta equivalente: se detecta por platos típicos "de cuchara"/horno.
            name_regex=(
                r"\b(?:sopa|caldo|guiso|guisado|estofado|cocido|pozole|puchero|cazuela|crema|"
                r"lasana|enchilada|pastel|pay|pure|gratinad[oa]|albondiga|frijol|lenteja|mole|"
                r"macarron|pasta|arroz con leche|chocolate caliente)(?:s|es)?\b"
            ),
            query_terms="guiso caldo sopa crema estofado",
        ),
        MoodRule(
            key="dulce",
            label="Dulce",
            categories=frozenset({"postre"}),
            query_terms="postre dulce chocolate azucar",
        ),
        MoodRule(
            key="picante",
            label="Picante",
            # Sin etiqueta equivalente: se busca chile/picante en nombre o ingredientes.
            text_regex=(
                r"\b(?:chile|picante|jalapeno|habanero|serrano|chipotle|cayena|guajillo|"
                r"pasilla|aji|piquin|tabasco|sriracha)(?:s|es)?\b"
            ),
            query_terms="picante chile jalapeno habanero chipotle",
        ),
        MoodRule(
            key="ligero",
            label="Ligero",
            tags=frozenset(
                {
                    "bajo en calorias",
                    "bajo en grasas",
                    "sin grasa",
                    "recomendada para perder peso",
                    "ensaladas",
                    "sopas",
                    "recetas al vapor",
                }
            ),
            name_regex=r"\b(?:ensalada|sopa|caldo|vapor|ligera|ligero|light|gazpacho|ceviche)(?:s|es)?\b",
            query_terms="ligero ensalada sopa vapor verduras",
        ),
    )
}


@dataclass(frozen=True)
class UserPreferences:
    """Preferencias ya validadas que recibe el recomendador."""

    moods: tuple[str, ...] = ()
    difficulty: str | None = None  # uno de DIFFICULTIES
    max_time: int | None = None  # minutos
    countries: tuple[str, ...] = ()  # vacío = cualquier país
    exclude_ids: tuple[int, ...] = field(default_factory=tuple)
    top_n: int = DEFAULT_TOP_N

    def __post_init__(self) -> None:
        unknown = [m for m in self.moods if m not in MOOD_RULES]
        if unknown:
            raise ValueError(f"Antojos desconocidos: {unknown}. Válidos: {sorted(MOOD_RULES)}")
        if self.difficulty is not None and self.difficulty not in DIFFICULTIES:
            raise ValueError(f"Dificultad desconocida: {self.difficulty!r}. Válidas: {DIFFICULTIES}")
        if self.top_n < 1:
            raise ValueError("top_n debe ser >= 1")
