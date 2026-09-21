from fastapi.testclient import TestClient
from app.main import app

def test_info_check():

    client = TestClient(app)
    response = client.get("/api/v1/info")
    
    assert response.status_code == 200
    assert response.json() == { "name": "IntelliDocs", "version": "0.1.0" }