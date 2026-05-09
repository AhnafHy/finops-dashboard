output "api_url" {
  value       = aws_api_gateway_stage.prod.invoke_url
  description = "FinOps Dashboard API base URL"
}

output "dynamodb_table" {
  value       = aws_dynamodb_table.cost_data.name
  description = "DynamoDB table storing cost data"
}

output "collector_function_name" {
  value       = aws_lambda_function.cost_collector.function_name
  description = "Cost collector Lambda function name"
}

output "api_function_name" {
  value       = aws_lambda_function.cost_api.function_name
  description = "Cost API Lambda function name"
}