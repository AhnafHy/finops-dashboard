import requests
import sys
import json
from datetime import datetime, timedelta

BASE_URL = sys.argv[1].rstrip('/') if len(sys.argv) > 1 else "http://localhost:5000"

print("=" * 60)
print("       AWS FINOPS COST REPORT")
print(f"       Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
print("=" * 60)

# Budget status
print("\n📊 BUDGET STATUS")
print("-" * 40)
r = requests.get(f"{BASE_URL}/budget/status")
if r.status_code == 200:
    b = r.json()
    status = "⚠️  OVER BUDGET" if b.get('is_over_budget') else "✅ WITHIN BUDGET"
    print(f"Status:           {status}")
    print(f"Month-to-date:    ${b.get('mtd_cost', 0):.4f}")
    print(f"Projected total:  ${b.get('projected_monthly_cost', 0):.4f}")
    print(f"Budget threshold: ${b.get('budget_threshold', 0):.2f}")
    print(f"Variance:         ${b.get('variance', 0):.4f}")
else:
    print("No budget data available — run the collector Lambda first")

# Top services
print("\n💰 TOP SERVICES (Last 7 Days)")
print("-" * 40)
r = requests.get(f"{BASE_URL}/costs/top-services?days=7")
if r.status_code == 200:
    data = r.json()
    services = data.get('top_services', [])
    if services:
        for i, s in enumerate(services[:5], 1):
            print(f"{i}. {s['service'][:40]:<40} ${s['total_cost']:.4f}")
    else:
        print("No service data available yet")

# Daily breakdown
print("\n📅 DAILY COST BREAKDOWN (Last 7 Days)")
print("-" * 40)
week_ago = (datetime.utcnow() - timedelta(days=7)).strftime('%Y-%m-%d')
yesterday = (datetime.utcnow() - timedelta(days=1)).strftime('%Y-%m-%d')
r = requests.get(f"{BASE_URL}/costs/range?start={week_ago}&end={yesterday}")
if r.status_code == 200:
    data = r.json()
    daily = data.get('daily_breakdown', [])
    if daily:
        for d in daily:
            bar_length = int(d['total_cost'] * 100)
            bar = '█' * min(bar_length, 40)
            print(f"{d['date']}  ${d['total_cost']:.4f}  {bar}")
        print(f"\nTotal (7 days):   ${data.get('total_cost', 0):.4f}")
    else:
        print("No daily data available yet")

print("\n" + "=" * 60)