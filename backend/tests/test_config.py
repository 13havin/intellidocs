import pytest

from app.core.config import validate_database_url, validate_secret_key, validate_algorithm

def test_algorithm_accepts_hs256():
    validate_algorithm("HS256")
    
@pytest.mark.parametrize("value", [None, "", " ", "HS512", "hs256"])
def test_algorithm_rejects_invalid_values(value):
    with pytest.raises(ValueError):
        validate_algorithm(value)
        
def test_secret_key_accepts_valid_key():
    validate_secret_key("2no>}7l[5*nr,0z2CzU[bY>=L3@I,-,u")
    
@pytest.mark.parametrize("value", [None, "", " ", "2no>}7l[5*"])
def test_secret_key_rejects_invalid_values(value):
    with pytest.raises(ValueError):
        validate_secret_key(value)
        
def test_database_url_accepts_valid_url():
    validate_database_url("postgresql://postgres:root@localhost:5432/intellidocs_test_db")
    
@pytest.mark.parametrize("value", [None, "", " ", "invalid_url", "postgresql://user:pass@localhost:5432", "postgr://user:pass@localhost:5432"])
def  test_database_url_rejects_invalid_values(value):
    with pytest.raises(ValueError):
        validate_database_url(value)