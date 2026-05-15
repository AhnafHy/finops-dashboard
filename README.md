# FinOps Cost Dashboard

A serverless AWS cost visibility and governance tool. A ambda function pulls daily spending data from the Cost Explorer API and stores cost snapshots in DynamoDB, a second Lambda exposes a REST API via API Gateway to query spending by service and time range, and CloudWatch alarms fire when projected monthly spend exceeds a configurable threshold. The entire pipeline runs on a daily EventBridge schedule and is fully provisioned via Terraform.

---

## What It Does

- **Daily cost collection** — Lambda queries Cost Explorer every 24 hours, storing per-service costs and daily totals in DynamoDB
- **Budget projection** — calculates month-to-date spend and projects end-of-month cost based on daily burn rate
- **REST API** — query daily costs, cost ranges, top services by spend, and live budget status via API Gateway endpoints
- **CloudWatch alarms** — fires when projected monthly spend exceeds the configured threshold, and monitors collector Lambda error rate
- **Cost report** — CLI script generates a formatted report showing budget status, top services, and a daily cost bar chart

---

## Architecture

```
                    ┌──────────────────────────────────────────────────┐
                    │                     AWS                          │
                    │                                                  │
                    │  EventBridge (rate: 1 day)                       │
                    │       │                                          │
                    │       ▼                                          │
                    │  Lambda — cost_collector                         │
                    │  Queries Cost Explorer API                       │
                    │  Stores per-service costs + daily totals         │
                    │  Calculates budget projection                    │
                    │       │                                          │
                    │       ▼                                          │
                    │  DynamoDB (cost-data table)                      │
                    │  pk: COST#YYYY-MM-DD                             │
                    │  sk: SERVICE#<service-name> | TOTAL              │
                    │  pk: BUDGET#YYYY-MM                              │
                    │  sk: PROJECTION                                  │
                    │       │                                          │
                    │       ▼                                          │
                    │  Lambda — cost_api                               │
                    │  Handles REST API requests                       │
                    │       │                                          │
                    │       ▼                                          │
                    │  API Gateway (REST API)                          │
                    │  /health /costs/daily /costs/range               │
                    │  /costs/top-services /budget/status              │
                    │                                                  │
                    │  CloudWatch Alarms                               │
                    │  Budget exceeded + collector errors              │
                    └──────────────────────────────────────────────────┘

All infrastructure provisioned via Terraform
```
> **Note:** Cost data reflects actual AWS account spend via the Cost Explorer API, on a new account with minimal activity this will show near-zero values. In a production environment with real workloads the dashboard surfaces meaningful spending patterns, anomalies, and projected overruns. The architecture scales to any account size without code changes.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Cost Data Source | AWS Cost Explorer API |
| Collection & API | AWS Lambda (Python 3.11) |
| Storage | AWS DynamoDB (PAY_PER_REQUEST) |
| API | AWS API Gateway (REST) |
| Scheduling | AWS EventBridge (rate: 1 day) |
| Observability | AWS CloudWatch Alarms |
| Infrastructure as Code | Terraform |
| Language | Python 3.11 |

---

## Project Structure

```
finops-dashboard/
├── terraform/
│   ├── main.tf             # All AWS resources — DynamoDB, Lambda x2, API Gateway, EventBridge, IAM, CloudWatch
│   ├── variables.tf        # Configurable variables (region, budget threshold, collection schedule)
│   └── outputs.tf          # API URL, DynamoDB table name, Lambda function names
├── lambda/
│   ├── cost_collector.py   # Pulls Cost Explorer data, stores in DynamoDB, calculates budget projection
│   └── cost_api.py         # REST API handler — daily costs, ranges, top services, budget status
├── scripts/
│   ├── test_api.py         # Full API test suite validating all endpoints and status codes
│   └── generate_report.py  # CLI cost report — budget status, top services, daily bar chart
├── .gitignore
└── README.md
```

---

## DynamoDB Data Model

| pk | sk | Description |
|---|---|---|
| `COST#2026-05-08` | `SERVICE#Amazon EC2` | Per-service daily cost |
| `COST#2026-05-08` | `TOTAL` | Daily total across all services |
| `BUDGET#2026-05` | `PROJECTION` | MTD cost and projected month-end |

---

## API Reference

### GET /health
```json
{"status": "ok"}
```

### GET /costs/daily?date=2026-05-08
Returns per-service cost breakdown for a specific date, sorted by cost descending.
```json
{
  "date": "2026-05-08",
  "total_cost": 0.13,
  "services": [
    {"service": "Amazon EC2", "cost": 0.08, "unit": "USD"},
    {"service": "Amazon RDS", "cost": 0.05, "unit": "USD"}
  ]
}
```

### GET /costs/range?start=2026-05-01&end=2026-05-08
Returns daily totals across a date range with aggregate total.

### GET /costs/top-services?days=7
Returns top 10 services by total spend over the specified period.

### GET /budget/status
```json
{
  "month": "2026-05",
  "mtd_cost": 0.13,
  "projected_monthly_cost": 0.58,
  "budget_threshold": 50.0,
  "is_over_budget": false,
  "variance": -49.42
}
```

---

## How to Deploy

### Prerequisites
- [AWS account](https://aws.amazon.com) with IAM credentials configured
- [Terraform](https://developer.hashicorp.com/terraform/install) installed
- [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) installed and configured
- [Python 3.11+](https://www.python.org/downloads/) and boto3, requests installed

### Steps

**1. Clone the repository**
```bash
git clone https://github.com/AhnafHy/finops-dashboard.git
cd finops-dashboard
```

**2. Deploy infrastructure**
```bash
cd terraform
terraform init
terraform apply
```
Note the `api_url` output — this is your API base URL.

**3. Trigger the collector manually**

Go to AWS Console → Lambda → `finops-dashboard-collector` → Test → run with empty JSON `{}`.

**4. Install dependencies**
```bash
pip install boto3 requests
```

**5. Run the API test suite**
```bash
cd ..
python scripts/test_api.py YOUR_API_URL
```

**6. Generate the cost report**
```bash
python scripts/generate_report.py YOUR_API_URL
```

**7. Clean up**
```bash
cd terraform
terraform destroy
```

---

## Screenshots

**API test suite — all endpoints passing:**

<img width="259" height="726" alt="api-tests" src="https://github.com/user-attachments/assets/c7bd2774-44ae-4fd1-b13c-20afa9b870cf" />


**CLI cost report — budget status, top services, daily breakdown:**

<img width="1730" height="523" alt="cost-report" src="https://github.com/user-attachments/assets/18c3d4f0-084b-4d80-b48d-4284c0d6d911" />


**DynamoDB table — cost records with per-service and daily total breakdown:**

<img width="1238" height="614" alt="dynamodb" src="https://github.com/user-attachments/assets/757cd6c9-eec2-48dc-b50f-3216a72dfb85" />


**CloudWatch alarms — collector errors OK, budget alarm configured:**

<img width="1632" height="219" alt="cloudwatch alarms" src="https://github.com/user-attachments/assets/1f5aa0f7-6582-4ec6-9912-0be587d0ed9a" />


---

## Key Concepts Demonstrated

- **Cost Explorer API integration** — programmatic access to AWS billing data with per-service granularity and daily breakdowns
- **FinOps data modeling** — DynamoDB composite key design separating service-level costs, daily totals, and budget projections into queryable records
- **Budget projection** — linear extrapolation of month-to-date spend to forecast end-of-month cost and compare against threshold
- **Serverless API** — Lambda + API Gateway REST endpoints with proper HTTP status codes and CORS headers
- **EventBridge scheduling** — daily automated cost collection without managing servers or cron jobs
- **CloudWatch governance** — billing alarm on `EstimatedCharges` metric plus Lambda error rate monitoring for pipeline reliability
- **Infrastructure as code** — all resources provisioned and reproducible via Terraform with configurable budget threshold
