import sys
import asyncio
from datetime import datetime, timezone
from httpx import AsyncClient, ASGITransport
from app.main import app

async def test_full_flow():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Login Lawyer (Advocate Ananya Roy)
        res = await client.post("/api/v1/auth/login", json={"email": "advocate@lcc.test", "password": "Password123!"})
        assert res.status_code == 200, f"Lawyer login failed: {res.text}"
        lawyer_token = res.json()["access_token"]
        lawyer_headers = {"Authorization": f"Bearer {lawyer_token}"}
        print("PASS: Lawyer logged in.")

        # 2. Lawyer Heartbeat
        res = await client.post("/api/v1/lawyers/heartbeat", headers=lawyer_headers)
        assert res.status_code == 200, f"Heartbeat failed: {res.text}"
        assert res.json()["is_online"] is True
        print("PASS: Lawyer heartbeat sent.")

        # 3. Login Client
        res = await client.post("/api/v1/auth/login", json={"email": "client@lcc.test", "password": "Password123!"})
        assert res.status_code == 200, f"Client login failed: {res.text}"
        client_token = res.json()["access_token"]
        client_headers = {"Authorization": f"Bearer {client_token}"}
        print("PASS: Client logged in.")

        # 4. Client searches for online lawyers
        res = await client.get("/api/v1/lawyers?online_only=true", headers=client_headers)
        assert res.status_code == 200, f"Search failed: {res.text}"
        online_lawyers = res.json().get("items", [])
        assert len(online_lawyers) >= 1, "Expected at least 1 online lawyer"
        found = any(l["full_name"] == "Advocate Ananya Roy" and l["is_online"] is True for l in online_lawyers)
        assert found, f"Ananya Roy not online in: {online_lawyers}"
        lawyer = next(l for l in online_lawyers if l["full_name"] == "Advocate Ananya Roy")
        lawyer_id = lawyer.get("user_id") or lawyer["id"]
        print(f"PASS: Lawyer Ananya Roy discovered online with user_id={lawyer_id}.")

        # 5. Client creates instant consultation
        now_iso = datetime.now(timezone.utc).isoformat()
        res = await client.post("/api/v1/consultations", headers=client_headers, json={
            "lawyer_id": lawyer_id,
            "scheduled_at": now_iso,
            "duration_minutes": 30,
            "is_instant": True,
        })
        assert res.status_code == 201, f"Consultation creation failed: {res.text}"
        consultation = res.json()
        consultation_id = consultation["id"]
        print(f"PASS: Instant consultation created with id={consultation_id}.")

        # 6. Client pays via test pay endpoint
        res = await client.post(f"/api/v1/consultations/{consultation_id}/pay-test", headers=client_headers)
        assert res.status_code == 200, f"Pay-test failed: {res.text}"
        assert res.json()["status"] == "PAID"
        print("PASS: Test payment authoritatively succeeded and marked PAID.")

        # 7. Lawyer polls incoming calls
        res = await client.get("/api/v1/consultations/incoming-calls", headers=lawyer_headers)
        assert res.status_code == 200, f"Incoming calls poll failed: {res.text}"
        incoming = res.json()
        assert any(c["id"] == consultation_id for c in incoming), f"Consultation {consultation_id} not in incoming: {incoming}"
        print("PASS: Consultation appeared in Lawyer incoming calls feed.")

        # 8. Lawyer accepts consultation
        res = await client.post(f"/api/v1/consultations/{consultation_id}/accept", headers=lawyer_headers)
        assert res.status_code == 200, f"Accept failed: {res.text}"
        print("PASS: Consultation accepted by Lawyer.")

        # 9. Client requests video join token (GET endpoint)
        res = await client.get(f"/api/v1/consultations/{consultation_id}/video/join", headers=client_headers)
        assert res.status_code == 200, f"Client join failed: {res.text}"
        join_data = res.json()
        assert "token" in join_data and "room_id" in join_data
        print("PASS: Video meeting join token issued successfully (no early-join blockage).")

        print("\nALL 9 INTEGRATION CHECKS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    asyncio.run(test_full_flow())
