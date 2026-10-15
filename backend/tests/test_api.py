from fastapi.testclient import TestClient

from app.main import app


def test_health_and_overview_and_settings():
    with TestClient(app) as client:
        assert client.get("/api/crm/health").json() == {"status": "ok"}
        ov = client.get("/api/crm/overview")
        assert ov.status_code == 200, ov.text
        body = ov.json()
        assert body["followers"] == 0 and body["jobs"]["queued"] == 0
        st = client.get("/api/crm/settings").json()
        assert st["values"]["source_lists"] == "fake"
        upd = client.put("/api/crm/settings", json={"values": {"followback_deadline_days": 10, "twitterapi_io_key": "abcd1234efgh"}})
        assert upd.status_code == 200, upd.text
        assert upd.json()["values"]["followback_deadline_days"] == 10
        assert upd.json()["values"]["twitterapi_io_key"] == "abcd…efgh"
        # echoing the mask back must not clobber the secret
        again = client.put("/api/crm/settings", json={"values": {"twitterapi_io_key": "abcd…efgh"}})
        assert again.json()["values"]["twitterapi_io_key"] == "abcd…efgh"
        job = client.post("/api/crm/syncs/run")
        assert job.status_code == 202 and job.json()["type"] == "sync_full"
        dup = client.post("/api/crm/syncs/run")
        assert dup.json()["id"] == job.json()["id"]  # deduped while queued
        lst = client.get("/api/crm/people?relation=mutual&sort=-followers&page_size=5")
        assert lst.status_code == 200 and lst.json()["total"] == 0
        bad = client.get("/api/crm/people?relation=nonsense")
        assert bad.status_code == 422
