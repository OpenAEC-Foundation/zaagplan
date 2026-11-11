"""Tests voor /v1 en de sleutelcontrole. Draai vanuit backend/: python -m pytest tests"""

import hashlib
import importlib
import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

SLEUTEL = "geheim-voor-de-test"
OPDRACHT = {
    "parts": [{"id": "a", "length": 1200, "quantity": 3}, {"id": "b", "length": 800, "quantity": 2}],
    "stocks": [{"id": "s", "length": 3000}],
    "algorithm": "ffd",
}


def laad(sleutels):
    if sleutels is None:
        os.environ.pop("OPENAEC_API_SLEUTELS", None)
    else:
        os.environ["OPENAEC_API_SLEUTELS"] = sleutels
    for naam in ("main", "toegang", "api_v1"):
        sys.modules.pop(naam, None)
    return TestClient(importlib.import_module("main").app)


@pytest.fixture
def beveiligd():
    yield laad(hashlib.sha256(SLEUTEL.encode()).hexdigest())
    os.environ.pop("OPENAEC_API_SLEUTELS", None)


def test_zonder_sleutels_open():
    c = laad(None)
    assert c.post("/optimize/1d", json=OPDRACHT).status_code == 200
    assert c.post("/v1/optimize/1d", json=OPDRACHT).status_code == 200


def test_health_en_openapi_zonder_sleutel(beveiligd):
    assert beveiligd.get("/v1/health").json()["status"] == "ok"
    assert "/v1/optimize/1d" in beveiligd.get("/v1/openapi.json").json()["paths"]


def test_sleutel_verplicht(beveiligd):
    r = beveiligd.post("/v1/optimize/1d", json=OPDRACHT)
    assert r.status_code == 401 and r.headers["www-authenticate"] == "Bearer"
    assert beveiligd.post("/optimize/1d", json=OPDRACHT).status_code == 401
    fout = {"Authorization": "Bearer niet-goed"}
    assert beveiligd.post("/v1/optimize/1d", json=OPDRACHT, headers=fout).status_code == 401


def test_rekenen_met_sleutel(beveiligd):
    r = beveiligd.post("/v1/optimize/1d", json=OPDRACHT, headers={"Authorization": f"Bearer {SLEUTEL}"})
    assert r.status_code == 200
    geplaatst = sum(len(p["cuts"]) for p in r.json()["plans"])
    assert geplaatst == 5 and not r.json()["parts_not_placed"]


def test_tools_zonder_bevestigen(beveiligd):
    tools = beveiligd.get("/v1/tools", headers={"Authorization": f"Bearer {SLEUTEL}"}).json()["tools"]
    assert {t["name"] for t in tools} == {"zaagplan_algoritmen", "zaagplan_optimaliseer_1d"}
    assert not any(t.get("bevestigen") for t in tools)


def test_foute_hash_stopt_starten():
    with pytest.raises(RuntimeError):
        laad("zz")
    os.environ.pop("OPENAEC_API_SLEUTELS", None)
