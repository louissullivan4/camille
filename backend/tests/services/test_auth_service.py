import uuid
from unittest.mock import patch

import pytest
from jose import JWTError

from app.services.auth_service import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_hash_password_produces_bcrypt_hash() -> None:
    hashed = hash_password("supersecret")
    assert hashed.startswith("$2b$")
    assert hashed != "supersecret"


def test_verify_password_correct() -> None:
    hashed = hash_password("mypassword")
    assert verify_password("mypassword", hashed) is True


def test_verify_password_wrong() -> None:
    hashed = hash_password("mypassword")
    assert verify_password("wrongpassword", hashed) is False


def test_create_and_decode_token_roundtrip() -> None:
    user_id = uuid.uuid4()
    org_id = uuid.uuid4()
    token = create_access_token(user_id, "org_manager", org_id)
    payload = decode_access_token(token)
    assert payload["sub"] == str(user_id)
    assert payload["role"] == "org_manager"
    assert payload["org"] == str(org_id)


def test_create_token_with_no_org() -> None:
    user_id = uuid.uuid4()
    token = create_access_token(user_id, "admin", None)
    payload = decode_access_token(token)
    assert payload["sub"] == str(user_id)
    assert payload["org"] is None


def test_decode_invalid_token_raises_jwt_error() -> None:
    with pytest.raises(JWTError):
        decode_access_token("not.a.valid.token")


def test_decode_expired_token_raises_jwt_error() -> None:
    user_id = uuid.uuid4()
    # Patch JWT_EXPIRE_MINUTES to -1 so the token is already expired
    with patch("app.services.auth_service.settings") as mock_settings:
        mock_settings.JWT_SECRET = "test-secret"
        mock_settings.JWT_ALGORITHM = "HS256"
        mock_settings.JWT_EXPIRE_MINUTES = -1
        token = create_access_token(user_id, "admin", None)

    with patch("app.services.auth_service.settings") as mock_settings:
        mock_settings.JWT_SECRET = "test-secret"
        mock_settings.JWT_ALGORITHM = "HS256"
        with pytest.raises(JWTError):
            decode_access_token(token)
