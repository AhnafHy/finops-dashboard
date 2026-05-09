import requests
import sys
import json
from datetime import datetime, timedelta

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5000"
BASE_URL = BASE_URL.rstrip('/')

def test(name, response, expected_status):
    status = "PASS" if response.status_code == expected_status else "FAIL"
    print(f"[{status}] {name}: HTTP {response.status_code}")
    if status == "PASS":
        try:
            data = response.json()
            print(f"       {json.dumps(data, indent=2)[:300]}")
        except:
            pass
    else:
        print(f"       {response.text[:200]}")

yesterday = (datetime.utcnow() - timedelta(days=1)).strftime('%Y-%m-%d')
week_ago = (datetime.utcnow() - timedelta(days=7)).strftime('%Y-%m-%d')

print(f"\nTesting FinOps API at {BASE_URL}\n")

test("Health check",
     requests.get(f"{BASE_URL}/health"), 200)

test("Daily costs (yesterday)",
     requests.get(f"{BASE_URL}/costs/daily?date={yesterday}"), 200)

test("Cost range (last 7 days)",
     requests.get(f"{BASE_URL}/costs/range?start={week_ago}&end={yesterday}"), 200)

test("Top services (last 7 days)",
     requests.get(f"{BASE_URL}/costs/top-services?days=7"), 200)

test("Budget status",
     requests.get(f"{BASE_URL}/budget/status"), 200)

test("Invalid endpoint",
     requests.get(f"{BASE_URL}/invalid"), 404)

print("\nAll tests complete")