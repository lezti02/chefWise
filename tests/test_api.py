"""Pruebas de la API contra el CSV y los artefactos REALES (sin mocks)."""

from __future__ import annotations

SURPRISE_DEFAULT = {"antojos": ["rapido"], "difficulty": "facil", "max_time": 30, "top_n": 12}


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_recommendations_returns_n_real_recipes(client, csv_df):
    response = client.post("/recommendations", json=SURPRISE_DEFAULT)
    assert response.status_code == 200
    body = response.json()

    recs = body["recommendations"]
    assert len(recs) == SURPRISE_DEFAULT["top_n"]

    ids = [r["recipe_id"] for r in recs]
    assert len(set(ids)) == len(ids)
    assert set(ids) <= set(csv_df["recipe_id"])

    names = csv_df.set_index("recipe_id")["name"]
    for rec in recs:
        assert rec["name"] == names[rec["recipe_id"]]
        assert rec["ingredients"], "las recetas recomendadas deben traer ingredientes del CSV"


def test_recommendations_respect_time_and_difficulty(client):
    body = client.post(
        "/recommendations",
        json={"antojos": ["rapido"], "difficulty": "facil", "max_time": 20, "top_n": 30},
    ).json()
    assert body["meta"]["applied_max_time"] == 20
    for rec in body["recommendations"]:
        assert rec["total_time_min"] is not None and rec["total_time_min"] <= 20
        assert rec["difficulty"] == "facil"


def test_quick_mood_caps_time_at_30_even_with_larger_slider(client):
    body = client.post("/recommendations", json={"antojos": ["rapido"], "max_time": 90, "top_n": 30}).json()
    assert body["meta"]["applied_max_time"] == 30
    assert all(r["total_time_min"] <= 30 for r in body["recommendations"])


def test_recommendations_respect_country_and_exclusions(client):
    first = client.post("/recommendations", json={**SURPRISE_DEFAULT, "countries": ["México"]}).json()
    assert all(r["country"] == "México" for r in first["recommendations"])

    excluded = [r["recipe_id"] for r in first["recommendations"]]
    second = client.post(
        "/recommendations", json={**SURPRISE_DEFAULT, "countries": ["México"], "exclude_ids": excluded}
    ).json()
    assert second["recommendations"]
    assert not set(excluded) & {r["recipe_id"] for r in second["recommendations"]}


def test_moods_map_to_dataset_values(client):
    dulce = client.post("/recommendations", json={"antojos": ["dulce"], "top_n": 20}).json()
    assert dulce["recommendations"]
    assert all(r["category"] == "postre" for r in dulce["recommendations"])

    picante = client.post("/recommendations", json={"antojos": ["picante"], "top_n": 20}).json()
    assert picante["meta"]["query_text"]
    assert picante["recommendations"]


def test_recommendations_sorted_by_score(client):
    recs = client.post("/recommendations", json={"antojos": ["saludable"], "top_n": 20}).json()["recommendations"]
    scores = [r["score"] for r in recs]
    assert scores == sorted(scores, reverse=True)
    assert all(r["similarity"] is not None for r in recs)


def test_recommendations_without_preferences_are_valid(client):
    response = client.post("/recommendations", json={})
    assert response.status_code == 200
    assert len(response.json()["recommendations"]) == 12


def test_recommendations_by_ingredients(client):
    response = client.post("/recommendations/by-ingredients", json={"ingredients": ["pollo", "jitomate"], "top_n": 5})
    assert response.status_code == 200
    recs = response.json()["recommendations"]
    assert len(recs) == 5
    assert all(r["similarity"] > 0 for r in recs)


def test_get_recipe_returns_real_recipe(client, csv_df):
    recipe_id = int(csv_df.iloc[0]["recipe_id"])
    row = csv_df.set_index("recipe_id").loc[recipe_id]

    response = client.get(f"/recipes/{recipe_id}")
    assert response.status_code == 200
    body = response.json()

    assert body["recipe_id"] == recipe_id
    assert body["name"] == row["name"]
    assert body["source_url"] == row["url"]
    assert len(body["ingredients"]) == len(row["ingredients"].split(" | "))
    assert body["ingredients"][0] == row["ingredients"].split(" | ")[0]
    # Los pasos son los del CSV (sin el prefijo de numeración "1 ").
    first_step = row["instructions"].split(" | ")[0]
    assert first_step.endswith(body["instructions"][0])
    assert len(body["instructions"]) == len(row["instructions"].split(" | "))


def test_get_recipe_with_missing_fields_uses_null_not_invented_text(client, csv_df):
    no_steps = csv_df[csv_df["instructions"].isna()]
    assert len(no_steps), "el CSV debería tener recetas sin instrucciones"
    body = client.get(f"/recipes/{int(no_steps.iloc[0]['recipe_id'])}").json()
    assert body["instructions"] == []


def test_every_recommended_recipe_can_be_opened(client):
    recs = client.post("/recommendations", json=SURPRISE_DEFAULT).json()["recommendations"]
    for rec in recs:
        detail = client.get(f"/recipes/{rec['recipe_id']}")
        assert detail.status_code == 200
        assert detail.json()["name"] == rec["name"]
        assert detail.json()["ingredients"] == rec["ingredients"]


def test_unknown_recipe_returns_404(client):
    response = client.get("/recipes/99999999")
    assert response.status_code == 404
    assert "99999999" in response.json()["detail"]


def test_invalid_requests_return_422(client):
    assert client.get("/recipes/abc").status_code == 422
    assert client.get("/recipes/0").status_code == 422
    assert client.post("/recommendations", json={"antojos": ["inventado"]}).status_code == 422
    assert client.post("/recommendations", json={"difficulty": "imposible"}).status_code == 422
    assert client.post("/recommendations", json={"max_time": -5}).status_code == 422
    assert client.post("/recommendations", json={"top_n": 0}).status_code == 422
    assert client.post("/recommendations", json={"campo_desconocido": 1}).status_code == 422
    assert client.post("/recommendations/by-ingredients", json={"ingredients": []}).status_code == 422


def test_model_failure_returns_safe_500(client):
    from fastapi.testclient import TestClient

    from backend.main import create_app

    class Boom:
        def recommend(self, prefs):
            raise RuntimeError("detalle interno secreto")

    app = create_app()
    with TestClient(app, raise_server_exceptions=False) as tc:
        tc.app.state.recommender = Boom()
        response = tc.post("/recommendations", json={})
    assert response.status_code == 500
    assert "secreto" not in response.text


def test_cors_allows_the_angular_dev_origin(client):
    response = client.options(
        "/recommendations",
        headers={
            "Origin": "http://localhost:4200",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:4200"

    blocked = client.options(
        "/recommendations",
        headers={"Origin": "http://evil.example", "Access-Control-Request-Method": "POST"},
    )
    assert "access-control-allow-origin" not in blocked.headers
