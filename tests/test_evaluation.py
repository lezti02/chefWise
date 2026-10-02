"""Pruebas de las métricas de ranking y del conjunto de evaluación (sin modelos ni red)."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from src.evaluation import (
    assign_dish_family,
    build_eval_set,
    evaluate,
    hit_rate_at_k,
    ndcg_at_k,
    paired_bootstrap,
    precision_at_k,
    random_baseline,
    recall_at_k,
    top_k_ids,
)

RANKED = [10, 11, 12, 13, 14]
RELEVANT = frozenset({11, 14, 99, 98})


def test_precision_recall_hit():
    assert precision_at_k(RANKED, RELEVANT, 5) == pytest.approx(2 / 5)
    assert precision_at_k(RANKED, RELEVANT, 2) == pytest.approx(1 / 2)
    assert recall_at_k(RANKED, RELEVANT, 5) == pytest.approx(2 / 4)
    assert recall_at_k(RANKED, RELEVANT, 1) == 0.0
    assert hit_rate_at_k(RANKED, RELEVANT, 1) == 0.0
    assert hit_rate_at_k(RANKED, RELEVANT, 2) == 1.0


def test_ndcg_by_hand():
    # aciertos en las posiciones 2 y 5 -> DCG = 1/log2(3) + 1/log2(6); ideal con 4 relevantes y K=5: 4 unos
    dcg = 1 / math.log2(3) + 1 / math.log2(6)
    idcg = sum(1 / math.log2(i + 2) for i in range(4))
    assert ndcg_at_k(RANKED, RELEVANT, 5) == pytest.approx(dcg / idcg)


def test_ndcg_is_one_for_perfect_ranking_and_zero_for_none():
    assert ndcg_at_k([11, 14, 99, 98, 1], RELEVANT, 5) == pytest.approx(1.0)
    assert ndcg_at_k([1, 2, 3, 4, 5], RELEVANT, 5) == 0.0


def test_top_k_excludes_query_and_breaks_ties_by_position():
    sims = np.array([0.9, 0.9, 0.5, 0.9])
    ids = np.array([100, 101, 102, 103])
    assert top_k_ids(sims, ids, 2, exclude_pos=0) == [101, 103]
    assert top_k_ids(sims, ids, 4) == [100, 101, 103, 102]


def test_dish_family_rules():
    assert assign_dish_family("Tacos de Cerdo con Salsa Roja", "comida") == "tacos"
    assert assign_dish_family("Ensalada de pasta", "comida") == "ensalada"
    assert assign_dish_family("Pollo en salsa de cebolla", "comida") is None
    assert assign_dish_family("Pastel de Chocolate", "postre") == "pastel_tarta"
    assert assign_dish_family("Pastel de Carne", "comida") is None  # dulce/salado ambiguo -> exige postre
    assert assign_dish_family("Tarta de queso", float("nan")) is None


def _toy_catalog(n_per_family: int = 30) -> pd.DataFrame:
    rows = []
    for family_name in ("Tacos", "Ensalada", "Pizza"):
        for i in range(n_per_family):
            rows.append({"name": f"{family_name} numero {i}", "app_category": "comida"})
    df = pd.DataFrame(rows)
    df.insert(0, "recipe_id", np.arange(1, len(df) + 1))
    return df


def test_eval_set_is_deterministic_and_oracle_is_perfect():
    df = _toy_catalog()
    first = build_eval_set(df, seed=7, queries_per_group=5, min_group_size=20)
    second = build_eval_set(df, seed=7, queries_per_group=5, min_group_size=20)
    assert first.queries == second.queries
    assert len(first.queries) == 15

    ids = df["recipe_id"].to_numpy()
    id_to_pos = {int(r): i for i, r in enumerate(ids)}
    group_of = {rid: g for g, members in first.groups.items() for rid in members}

    def oracle(recipe_id: int, _pos: int) -> np.ndarray:
        return np.array([1.0 if group_of.get(int(r)) == group_of[recipe_id] else 0.0 for r in ids])

    result = evaluate(first, oracle, ids, id_to_pos, ks=(5, 10))
    assert (result["Precision@10"] == 1.0).all()
    assert (result["HitRate@5"] == 1.0).all()
    assert result["NDCG@10"].to_numpy() == pytest.approx(1.0)


def test_random_baseline_matches_simulation():
    df = _toy_catalog()
    eval_set = build_eval_set(df, seed=1, queries_per_group=5, min_group_size=20)
    ids = df["recipe_id"].to_numpy()
    id_to_pos = {int(r): i for i, r in enumerate(ids)}
    rng = np.random.default_rng(0)
    runs = [
        evaluate(eval_set, lambda *_: rng.random(len(ids)), ids, id_to_pos, ks=(5,)).mean(numeric_only=True)
        for _ in range(300)
    ]
    simulated = pd.concat(runs, axis=1).mean(axis=1)
    expected = random_baseline(eval_set, len(df), ks=(5,))
    for metric, value in expected.items():
        assert simulated[metric] == pytest.approx(value, abs=0.02), metric


def test_paired_bootstrap_detects_a_consistent_gain():
    a = np.zeros(200)
    b = np.full(200, 0.1)
    mean, low, high = paired_bootstrap(a, b, n_resamples=500)
    assert mean == pytest.approx(0.1)
    assert low > 0 and high >= low
