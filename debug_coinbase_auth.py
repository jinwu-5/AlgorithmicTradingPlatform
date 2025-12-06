"""Complete debug script for Coinbase API authentication."""
import os
import time
import secrets
import jwt
import requests
from dotenv import load_dotenv
from cryptography.hazmat.primitives import serialization

# Load environment variables
load_dotenv()

api_key = os.getenv("COINBASE_API_KEY")
api_secret = os.getenv("COINBASE_API_SECRET")

print("=" * 80)
print("COINBASE API AUTHENTICATION DEBUG")
print("=" * 80)

# Step 1: Check credentials
print("\n[STEP 1] Checking credentials...")
print(f"API Key: {api_key[:50] if api_key else 'NOT FOUND'}...")
print(f"API Secret length: {len(api_secret) if api_secret else 0} chars")

if not api_key or not api_secret:
    print("\n❌ ERROR: Credentials not loaded from .env file")
    exit(1)

# Step 2: Process the private key
print("\n[STEP 2] Processing private key...")
# Handle escaped newlines
if '\\n' in api_secret:
    print("   Converting \\n to actual newlines...")
    api_secret = api_secret.replace('\\n', '\n')

print(f"   Key starts with: {api_secret[:30]}")
print(f"   Key ends with: {api_secret[-30:]}")
print(f"   Contains BEGIN: {('BEGIN EC PRIVATE KEY' in api_secret)}")
print(f"   Contains END: {('END EC PRIVATE KEY' in api_secret)}")
print(f"   Line count: {len(api_secret.split(chr(10)))}")

# Step 3: Try to load the private key
print("\n[STEP 3] Loading private key...")
try:
    private_key_bytes = api_secret.encode('utf-8')
    private_key = serialization.load_pem_private_key(private_key_bytes, password=None)
    print("   ✓ Private key loaded successfully")
    print(f"   Key type: {type(private_key).__name__}")
except Exception as e:
    print(f"   ❌ ERROR loading private key: {e}")
    print("\n   Your private key format is incorrect. It should look like:")
    print('   -----BEGIN EC PRIVATE KEY-----')
    print('   MHcCAQEEI...')
    print('   -----END EC PRIVATE KEY-----')
    exit(1)

# Step 4: Build JWT
print("\n[STEP 4] Building JWT token...")
request_method = "GET"
request_host = "api.coinbase.com"
request_path = "/api/v3/brokerage/accounts"
uri = f"{request_method} {request_host}{request_path}"

print(f"   URI: {uri}")

current_time = int(time.time())
jwt_payload = {
    'sub': api_key,
    'iss': "cdp",
    'nbf': current_time,
    'exp': current_time + 120,
    'uri': uri,
}

jwt_headers = {
    'kid': api_key,
    'nonce': secrets.token_hex()
}

print(f"   Payload: {jwt_payload}")
print(f"   Headers (kid): {api_key[:50]}...")
print(f"   Headers (nonce): {jwt_headers['nonce'][:20]}...")

try:
    jwt_token = jwt.encode(
        jwt_payload,
        private_key,
        algorithm='ES256',
        headers=jwt_headers,
    )
    print(f"   ✓ JWT created successfully")
    print(f"   Token (first 100 chars): {jwt_token[:100]}...")
    print(f"   Token length: {len(jwt_token)} chars")
except Exception as e:
    print(f"   ❌ ERROR creating JWT: {e}")
    exit(1)

# Step 5: Make actual API request
print("\n[STEP 5] Making API request...")
url = f"https://{request_host}{request_path}"
headers = {
    "Authorization": f"Bearer {jwt_token}",
    "Accept": "application/json",
    "Content-Type": "application/json",
}

print(f"   URL: {url}")
print(f"   Authorization header: Bearer {jwt_token[:50]}...")

try:
    response = requests.get(url, headers=headers, timeout=10)
    print(f"\n   Response Status: {response.status_code}")
    print(f"   Response Headers: {dict(response.headers)}")

    if response.status_code == 200:
        print("\n✅ SUCCESS! Authentication working correctly")
        print(f"   Response: {response.json()}")
    else:
        print(f"\n❌ ERROR: {response.status_code}")
        print(f"   Response body: {response.text}")

        if response.status_code == 401:
            print("\n   TROUBLESHOOTING 401 Unauthorized:")
            print("   1. Verify your API key format: organizations/{org_id}/apiKeys/{key_id}")
            print("   2. Ensure you created the key with ECDSA (ES256), NOT Ed25519")
            print("   3. Check that the key has proper permissions")
            print("   4. Verify the key is not expired or revoked")
            print("   5. Make sure you're using the correct Coinbase product")
            print("      (Advanced Trade API, not Coinbase Exchange or Pro)")

except Exception as e:
    print(f"\n❌ Request failed: {e}")
    import traceback

    traceback.print_exc()

print("\n" + "=" * 80)
print("DEBUG COMPLETE")
print("=" * 80)