#!/usr/bin/env python3
"""
Test script to verify the NEOD purchase API endpoint is accessible.
This helps diagnose if the 403 error is coming from Flask or Cloudflare.
"""

import requests
import json

# Test the API endpoint locally (bypassing Cloudflare)
LOCAL_URL = "http://localhost:5000/api/v1/neod/purchase"

# Test data (this will fail validation, but should not return 403)
test_payload = {
    "signature": "test_signature_12345",
    "recipient": "11111111111111111111111111111111"
}

headers = {
    "Content-Type": "application/json",
    "X-Requested-With": "XMLHttpRequest"
}

print("Testing NEOD purchase API endpoint...")
print(f"URL: {LOCAL_URL}")
print(f"Payload: {json.dumps(test_payload, indent=2)}")
print(f"Headers: {json.dumps(headers, indent=2)}")
print("\n" + "="*60 + "\n")

try:
    response = requests.post(LOCAL_URL, json=test_payload, headers=headers)
    print(f"Status Code: {response.status_code}")
    print(f"Response Headers: {dict(response.headers)}")
    print(f"\nResponse Body:")
    try:
        print(json.dumps(response.json(), indent=2))
    except:
        print(response.text)
    
    print("\n" + "="*60 + "\n")
    
    if response.status_code == 403:
        print("❌ ERROR: Got 403 Forbidden!")
        print("This means Flask is blocking the request.")
        print("Check Flask logs for more details.")
    elif response.status_code == 404:
        print("❌ ERROR: Got 404 Not Found!")
        print("The API endpoint might not be registered correctly.")
    elif response.status_code in [400, 422, 503]:
        print("✅ SUCCESS: API endpoint is accessible!")
        print(f"Got expected error code {response.status_code} (validation/service error)")
        print("The 403 error is likely coming from Cloudflare, not Flask.")
    else:
        print(f"ℹ️  Got status code {response.status_code}")
        print("Check if this is expected for your test data.")
        
except requests.exceptions.ConnectionError:
    print("❌ ERROR: Could not connect to Flask app!")
    print("Make sure Flask is running on port 5000.")
except Exception as e:
    print(f"❌ ERROR: {type(e).__name__}: {e}")

print("\n" + "="*60)
print("\nNext Steps:")
print("1. If you got 403 here, the issue is in Flask (check logs)")
print("2. If you got 400/404/422/503, the issue is likely Cloudflare")
print("3. Check Cloudflare Dashboard → Security → Events for blocked requests")
print("4. See NEOD_403_FIX.md for Cloudflare configuration steps")
