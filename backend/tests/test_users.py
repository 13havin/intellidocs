from fastapi.testclient import TestClient
from app.main import app

def test_user_creation():

    client = TestClient(app)
    test_user_data = {"name": "test", "email": "test@ex.com"}
    response = client.post("/api/v1/users", json=test_user_data)
    
    assert response.status_code == 201
    assert response.json() == { "id": 1, "name": test_user_data["name"], "email": test_user_data["email"] }
    
def test_user_creation_invalid_email():

    client = TestClient(app)
    test_user_data = {"name": "test", "email": "invalid-email"}
    response = client.post("/api/v1/users", json=test_user_data)
    
    assert response.status_code == 422