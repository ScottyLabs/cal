"""TokenVerifier: only genuine Keycloak access tokens for this client pass."""

import time

import jwt
import pytest

from app.utils.auth import AuthError, TokenVerifier


def test_valid_token(verifier, make_token):
    claims = verifier.verify(make_token())
    assert claims["sub"] == "sub-alice"


def test_audience_may_name_the_client_instead_of_azp(verifier, make_token):
    token = make_token(azp="some-other-client", aud=[verifier.client_id, "account"])
    assert verifier.verify(token)["sub"] == "sub-alice"


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"exp": int(time.time()) - 120}, "expired"),
        ({"iss": "https://idp.scottylabs.org/realms/other"}, "issuer"),
        ({"azp": "study", "aud": "account"}, "not issued to this client"),
        ({"typ": "ID"}, "Not an access token"),
        ({"typ": "Refresh"}, "Not an access token"),
        ({"exp": None}, "exp"),
        ({"sub": None}, "sub"),
    ],
)
def test_rejects_bad_claims(verifier, make_token, overrides, message):
    with pytest.raises(AuthError) as err:
        verifier.verify(make_token(**overrides))
    assert err.value.status == 401
    assert message in err.value.message


def test_rejects_token_signed_by_another_key(verifier, make_token, attacker_key):
    # Same kid as the real key, so this exercises the signature check itself.
    with pytest.raises(AuthError):
        verifier.verify(make_token(key=attacker_key))


@pytest.mark.parametrize("token", ["", "not-a-jwt", "a.b.c"])
def test_rejects_garbage(verifier, token):
    with pytest.raises(AuthError):
        verifier.verify(token)


def test_jwks_unreachable_is_503_not_401(verifier, make_token):
    def down():
        raise jwt.PyJWKClientConnectionError("keycloak down")

    verifier.jwks.fetch_data = down
    with pytest.raises(AuthError) as err:
        verifier.verify(make_token())
    assert err.value.status == 503


def test_settings_from_env():
    v = TokenVerifier.from_env(
        {
            "KEYCLOAK_URL": "https://idp.scottylabs.org/",
            "KEYCLOAK_REALM": "scottylabs",
            "OIDC_CLIENT_ID": "cal",
        }
    )
    assert v.issuer == "https://idp.scottylabs.org/realms/scottylabs"
    assert "User-Agent" in v.jwks.headers  # Cloudflare 403s urllib's default
    with pytest.raises(RuntimeError, match="OIDC_CLIENT_ID"):
        TokenVerifier.from_env({"KEYCLOAK_URL": "x", "KEYCLOAK_REALM": "y"})
