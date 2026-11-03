from fastapi.testclient import TestClient
from alibi.main import app


# Creating a TestClient that sends Requests straight to the App, without starting a Server.
client = TestClient(app)

# Defining a Test Function to check that the Health Endpoint answers with the 'OK!' Status.
def test_health_returns_ok():
    response = client.get("/api/health/")

    assert response.status_code == 200
    assert response.json() == {"status": "OK!"}
