import unittest

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

import utils.coinbase_auth as coinbase_auth


class CoinbaseAuthTests(unittest.TestCase):
    def setUp(self):
        self.original_key = coinbase_auth.COINBASE_API_KEY
        self.original_secret = coinbase_auth.COINBASE_API_SECRET

        private_key = ec.generate_private_key(ec.SECP256R1())
        pem_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )

        coinbase_auth.COINBASE_API_KEY = "test-key"
        coinbase_auth.COINBASE_API_SECRET = pem_bytes.decode("utf-8")
        coinbase_auth._load_private_key.cache_clear()

    def tearDown(self):
        coinbase_auth.COINBASE_API_KEY = self.original_key
        coinbase_auth.COINBASE_API_SECRET = self.original_secret
        coinbase_auth._load_private_key.cache_clear()

    def _decode_payload(self, token: str) -> dict:
        return jwt.decode(token, options={"verify_signature": False}, algorithms=["ES256"])

    def test_uri_uses_host_and_path(self):
        token = coinbase_auth.build_coinbase_jwt(
            "get",
            "/api/v3/brokerage/products/BTC-USD/candles?start=1&end=2",
            "api.coinbase.com",
        )
        payload = self._decode_payload(token)
        self.assertEqual(
            payload["uri"],
            "GET api.coinbase.com/api/v3/brokerage/products/BTC-USD/candles?start=1&end=2",
        )

    def test_uri_handles_missing_leading_slash(self):
        token = coinbase_auth.build_coinbase_jwt("POST", "orders", "api.coinbase.com")
        payload = self._decode_payload(token)
        self.assertEqual(payload["uri"], "POST api.coinbase.com/orders")

    def test_host_sanitization(self):
        token = coinbase_auth.build_coinbase_jwt("POST", "/orders", "https://api.coinbase.com/")
        payload = self._decode_payload(token)
        self.assertEqual(payload["uri"], "POST api.coinbase.com/orders")


if __name__ == "__main__":
    unittest.main()
