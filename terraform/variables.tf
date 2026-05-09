variable "aws_region" {
  default = "us-east-1"
}

variable "project_name" {
  default = "finops-dashboard"
}

variable "monthly_budget_threshold" {
  description = "Monthly spend threshold in USD before alarm fires"
  default     = "50.0"
}

variable "collection_schedule" {
  description = "How often to collect cost data"
  default     = "rate(1 day)"
}