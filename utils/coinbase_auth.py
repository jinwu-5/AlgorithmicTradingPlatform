"""Coinbase JWT authentication utilities."""
import time
import secrets
import jwt
from cryptography.hazmat.primitives import serialization


def build_coinbase_jwt(key_name: str, key_secret: str, uri: str) -> str:
    """
    Build a JWT token for Coinbase Advanced Trade API authentication.

    Args:
        key_name: API key name in format "organizations/{org_id}/apiKeys/{key_id}"
        key_secret: Private key in PEM format (must be ECDSA/ES256, not Ed25519)
                   Should already have actual newlines, not escaped \n
        uri: Request URI in format "{METHOD} {HOST}{PATH}?{QUERY}"
             Example: "GET api.coinbase.com/api/v3/brokerage/accounts"

    Returns:
        JWT token string
    """
    # Load the private key (newlines should already be converted in settings.py)
    private_key_bytes = key_secret.encode('utf-8')
    private_key = serialization.load_pem_private_key(private_key_bytes, password=None)

    # Build JWT payload
    current_time = int(time.time())
    jwt_payload = {
        'sub': key_name,           # Subject: API key name
        'iss': "cdp",              # Issuer: Coinbase Developer Platform
        'nbf': current_time,       # Not before: current time
        'exp': current_time + 120, # Expires: 2 minutes from now
        'uri': uri,                # URI being requested
    }

    # Build JWT headers
    jwt_headers = {
        'kid': key_name,           # Key ID
        'nonce': secrets.token_hex() # Random nonce for security
    }

    # Generate and return the JWT using ES256 algorithm
    jwt_token = jwt.encode(
        jwt_payload,
        private_key,
        algorithm='ES256',
        headers=jwt_headers,
    )

    return jwt_token