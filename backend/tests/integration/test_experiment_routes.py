from sqlalchemy import select

from app.domain.creator.models import Creator
from app.infrastructure.db.session import AsyncSessionLocal


async def _create_creator_and_get_user_id(client, **overrides):
    payload = {"email": "exp@example.com", "name": "Exp Creator", "niche": "personal finance"}
    payload.update(overrides)
    resp = await client.post("/creators", json=payload)
    assert resp.status_code == 201
    body = resp.json()
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Creator).where(Creator.id == body["id"]))
        user_id = result.scalar_one().user_id
    return body["id"], user_id


async def test_create_and_get_experiment(client):
    creator_id, user_id = await _create_creator_and_get_user_id(client)
    headers = {"X-Debug-User-Id": user_id}

    resp = await client.post(
        f"/creators/{creator_id}/experiments",
        json={"hypothesis": "Contrarian hooks improve retention.", "variable": "hook_type"},
        headers=headers,
    )
    assert resp.status_code == 201
    experiment = resp.json()
    assert experiment["status"] == "planned"

    detail_resp = await client.get(f"/creators/{creator_id}/experiments/{experiment['id']}", headers=headers)
    assert detail_resp.status_code == 200
    body = detail_resp.json()
    assert body["experiment"]["id"] == experiment["id"]
    assert body["results"] == []


async def test_get_unknown_experiment_is_404(client):
    creator_id, user_id = await _create_creator_and_get_user_id(client, email="exp2@example.com", name="Exp2")
    resp = await client.get(f"/creators/{creator_id}/experiments/exp_missing", headers={"X-Debug-User-Id": user_id})
    assert resp.status_code == 404


async def test_experiments_enforce_tenant_isolation(client):
    creator_id, _ = await _create_creator_and_get_user_id(client, email="exp3@example.com", name="Exp3")
    resp = await client.get(f"/creators/{creator_id}/experiments", headers={"X-Debug-User-Id": "usr_someone_else"})
    assert resp.status_code == 404


async def test_status_transition_rejects_invalid_move(client):
    creator_id, user_id = await _create_creator_and_get_user_id(client, email="exp4@example.com", name="Exp4")
    headers = {"X-Debug-User-Id": user_id}
    create_resp = await client.post(
        f"/creators/{creator_id}/experiments", json={"hypothesis": "h"}, headers=headers
    )
    experiment_id = create_resp.json()["id"]

    ok_resp = await client.patch(
        f"/creators/{creator_id}/experiments/{experiment_id}/status", json={"status": "completed"}, headers=headers
    )
    assert ok_resp.status_code == 200

    bad_resp = await client.patch(
        f"/creators/{creator_id}/experiments/{experiment_id}/status", json={"status": "running"}, headers=headers
    )
    assert bad_resp.status_code == 409


async def test_add_results_and_evaluate_skips_in_stub_mode(client):
    creator_id, user_id = await _create_creator_and_get_user_id(client, email="exp5@example.com", name="Exp5")
    headers = {"X-Debug-User-Id": user_id}
    create_resp = await client.post(
        f"/creators/{creator_id}/experiments",
        json={"hypothesis": "Contrarian hooks improve retention.", "variable": "hook_type"},
        headers=headers,
    )
    experiment_id = create_resp.json()["id"]

    for value, group in [(40.0, "test"), (44.0, "test"), (30.0, "control"), (32.0, "control")]:
        result_resp = await client.post(
            f"/creators/{creator_id}/experiments/{experiment_id}/results",
            json={"metric_name": "retention", "metric_value": value, "group": group},
            headers=headers,
        )
        assert result_resp.status_code == 201

    detail_resp = await client.get(f"/creators/{creator_id}/experiments/{experiment_id}", headers=headers)
    assert len(detail_resp.json()["results"]) == 4

    eval_resp = await client.post(f"/creators/{creator_id}/experiments/{experiment_id}/evaluate", headers=headers)
    assert eval_resp.status_code == 200
    body = eval_resp.json()
    assert body["stats"]["retention"]["adequate_evidence"] is True
    assert body["experiment"] is None  # stub mode: skipped rather than guessed
    assert any("skipped" in w.lower() or "not configured" in w.lower() for w in body["warnings"])


async def test_evaluate_with_thin_evidence_skips_gracefully(client):
    creator_id, user_id = await _create_creator_and_get_user_id(client, email="exp6@example.com", name="Exp6")
    headers = {"X-Debug-User-Id": user_id}
    create_resp = await client.post(
        f"/creators/{creator_id}/experiments", json={"hypothesis": "h"}, headers=headers
    )
    experiment_id = create_resp.json()["id"]

    await client.post(
        f"/creators/{creator_id}/experiments/{experiment_id}/results",
        json={"metric_name": "retention", "metric_value": 40.0, "group": "test"},
        headers=headers,
    )

    eval_resp = await client.post(f"/creators/{creator_id}/experiments/{experiment_id}/evaluate", headers=headers)
    assert eval_resp.status_code == 200
    body = eval_resp.json()
    assert body["experiment"] is None
    assert any("2 results" in w for w in body["warnings"])
