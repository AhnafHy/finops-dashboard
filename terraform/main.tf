provider "aws" {
  region = var.aws_region
}

# ─── DYNAMODB TABLE ─────────────────────────────────────────
resource "aws_dynamodb_table" "cost_data" {
  name         = "${var.project_name}-cost-data"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pk"
  range_key    = "sk"

  attribute {
    name = "pk"
    type = "S"
  }

  attribute {
    name = "sk"
    type = "S"
  }

  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }

  tags = { Name = "${var.project_name}-cost-data" }
}

# ─── IAM ROLE FOR LAMBDA ────────────────────────────────────
resource "aws_iam_role" "lambda_role" {
  name = "${var.project_name}-lambda-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "lambda_policy" {
  name = "${var.project_name}-lambda-policy"
  role = aws_iam_role.lambda_role.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:GetItem",
          "dynamodb:Query",
          "dynamodb:BatchWriteItem",
          "dynamodb:Scan"
        ]
        Resource = aws_dynamodb_table.cost_data.arn
      },
      {
        Effect   = "Allow"
        Action   = ["ce:GetCostAndUsage", "ce:GetCostForecast"]
        Resource = "*"
      }
    ]
  })
}

# ─── COST COLLECTOR LAMBDA ──────────────────────────────────
data "archive_file" "collector_zip" {
  type        = "zip"
  source_file = "${path.module}/../lambda/cost_collector.py"
  output_path = "${path.module}/../lambda/cost_collector.zip"
}

resource "aws_lambda_function" "cost_collector" {
  filename         = data.archive_file.collector_zip.output_path
  function_name    = "${var.project_name}-collector"
  role             = aws_iam_role.lambda_role.arn
  handler          = "cost_collector.lambda_handler"
  runtime          = "python3.11"
  timeout          = 60
  source_code_hash = data.archive_file.collector_zip.output_base64sha256

  environment {
    variables = {
      DYNAMODB_TABLE  = aws_dynamodb_table.cost_data.name
      MONTHLY_BUDGET  = var.monthly_budget_threshold
    }
  }

  tags = { Name = "${var.project_name}-collector" }
}

# ─── COST API LAMBDA ────────────────────────────────────────
data "archive_file" "api_zip" {
  type        = "zip"
  source_file = "${path.module}/../lambda/cost_api.py"
  output_path = "${path.module}/../lambda/cost_api.zip"
}

resource "aws_lambda_function" "cost_api" {
  filename         = data.archive_file.api_zip.output_path
  function_name    = "${var.project_name}-api"
  role             = aws_iam_role.lambda_role.arn
  handler          = "cost_api.lambda_handler"
  runtime          = "python3.11"
  timeout          = 30
  source_code_hash = data.archive_file.api_zip.output_base64sha256

  environment {
    variables = {
      DYNAMODB_TABLE = aws_dynamodb_table.cost_data.name
    }
  }

  tags = { Name = "${var.project_name}-api" }
}

# ─── API GATEWAY ────────────────────────────────────────────
resource "aws_api_gateway_rest_api" "api" {
  name = "${var.project_name}-api"
}

resource "aws_api_gateway_resource" "proxy" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  parent_id   = aws_api_gateway_rest_api.api.root_resource_id
  path_part   = "{proxy+}"
}

resource "aws_api_gateway_method" "proxy" {
  rest_api_id   = aws_api_gateway_rest_api.api.id
  resource_id   = aws_api_gateway_resource.proxy.id
  http_method   = "ANY"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "lambda" {
  rest_api_id             = aws_api_gateway_rest_api.api.id
  resource_id             = aws_api_gateway_resource.proxy.id
  http_method             = aws_api_gateway_method.proxy.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.cost_api.invoke_arn
}

resource "aws_api_gateway_stage" "prod" {
  deployment_id = aws_api_gateway_deployment.deployment.id
  rest_api_id   = aws_api_gateway_rest_api.api.id
  stage_name    = "prod"
}

resource "aws_api_gateway_deployment" "deployment" {
  depends_on  = [aws_api_gateway_integration.lambda]
  rest_api_id = aws_api_gateway_rest_api.api.id

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.cost_api.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.api.execution_arn}/*/*"
}

# ─── EVENTBRIDGE SCHEDULE ───────────────────────────────────
resource "aws_cloudwatch_event_rule" "daily_collection" {
  name                = "${var.project_name}-daily-collection"
  description         = "Trigger cost collection daily"
  schedule_expression = var.collection_schedule
}

resource "aws_cloudwatch_event_target" "collector" {
  rule      = aws_cloudwatch_event_rule.daily_collection.name
  target_id = "CostCollectorLambda"
  arn       = aws_lambda_function.cost_collector.arn
}

resource "aws_lambda_permission" "eventbridge" {
  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.cost_collector.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.daily_collection.arn
}

# ─── CLOUDWATCH ALARMS ──────────────────────────────────────
resource "aws_cloudwatch_metric_alarm" "budget_alarm" {
  alarm_name          = "${var.project_name}-budget-exceeded"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "EstimatedCharges"
  namespace           = "AWS/Billing"
  period              = 86400
  statistic           = "Maximum"
  threshold           = var.monthly_budget_threshold
  alarm_description   = "Monthly AWS spend has exceeded the configured budget threshold"

  dimensions = {
    Currency = "USD"
  }
}

resource "aws_cloudwatch_metric_alarm" "collector_errors" {
  alarm_name          = "${var.project_name}-collector-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 86400
  statistic           = "Sum"
  threshold           = 0
  alarm_description   = "Cost collector Lambda has errors"
  dimensions = {
    FunctionName = aws_lambda_function.cost_collector.function_name
  }
}