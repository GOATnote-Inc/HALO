"""API surface tests — standalone TestClient app; the router mounts into halo.app later."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from halo.edu.routes import router

app = FastAPI()
app.include_router(router)
client = TestClient(app)


def test_list_modules() -> None:
    body = client.get("/edu/modules").json()
    assert {m["id"] for m in body} == {
        "breech_delivery",
        "lateral_canthotomy",
        "organophosphate",
        "perimortem_cesarean",
    }
    assert all(m["review_status"] == "draft" for m in body)
    assert all("@v1+" in m["content_version"] for m in body)


def test_get_module_and_404() -> None:
    ok = client.get("/edu/modules/organophosphate")
    assert ok.status_code == 200
    assert ok.json()["name"].startswith("Organophosphate")
    assert client.get("/edu/modules/thoracotomy").status_code == 404


def test_card_and_index_are_html() -> None:
    card = client.get("/edu/modules/lateral_canthotomy/card")
    assert card.status_code == 200
    assert card.headers["content-type"].startswith("text/html")
    assert "DRAFT — PENDING PHYSICIAN REVIEW" in card.text
    index = client.get("/edu/")
    assert index.status_code == 200
    assert "procedure cards" in index.text


def test_find_ranks_and_never_guesses() -> None:
    hit = client.get("/edu/find", params={"q": "chemical explosion 2pam"}).json()
    assert hit["matches"][0]["id"] == "organophosphate"
    assert hit["routed_id"] is None  # llm off by default
    miss = client.get("/edu/find", params={"q": "zebra unicorn"}).json()
    assert miss["matches"] == []
    assert len(miss["all_module_ids"]) == 4  # the full list, not a guess


def test_dose_endpoint_computes_peds_antidotes() -> None:
    body = {"module_id": "organophosphate", "weight_kg": 22, "age_years": 6}
    doses = {d["med"]: d for d in client.post("/edu/dose", json=body).json()["doses"]}
    assert doses["Atropine"]["text"].startswith("1.1 mg")
    assert doses["Atropine"]["status"] == "computed"


def test_dose_endpoint_refuses_without_context() -> None:
    body = {"module_id": "organophosphate"}
    doses = client.post("/edu/dose", json=body).json()["doses"]
    refused = [d for d in doses if d["status"] == "refused"]
    assert refused and all(d["reason"] for d in refused)


def test_drill_grade_endpoint() -> None:
    answers = [
        "decon outside first, PPE",
        "atropine, double q5min until dry",
        "pralidoxime slow IV with atropine",
        "midazolam IM",
        "rocuronium",
        "three",
        "declare MCI, poison control",
    ]
    body = {"module_id": "organophosphate", "answers": answers, "trainee": "t"}
    result = client.post("/edu/drill/grade", json=body).json()
    assert result["passed"] is True
    assert result["score"] == 1.0


def test_drill_grade_critical_miss_fails() -> None:
    answers = ["bay 1 now"] + ["atropine"] * 6
    body = {"module_id": "organophosphate", "answers": answers}
    result = client.post("/edu/drill/grade", json=body).json()
    assert result["passed"] is False
    assert result["critical_misses"]


def test_drill_grade_wrong_answer_count_is_422() -> None:
    body = {"module_id": "organophosphate", "answers": ["one"]}
    assert client.post("/edu/drill/grade", json=body).status_code == 422


def test_drill_grade_oversized_answer_is_422() -> None:
    body = {"module_id": "organophosphate", "answers": ["x" * 6000] + ["ok"] * 6}
    assert client.post("/edu/drill/grade", json=body).status_code == 422
