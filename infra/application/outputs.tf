output "api_url" {
  description = "Base URL for the deployed HTTP API."
  value       = aws_apigatewayv2_api.vpc.api_endpoint
}

output "cognito_user_pool_id" {
  description = "User pool used to create API users."
  value       = aws_cognito_user_pool.api.id
}

output "cognito_client_id" {
  description = "Public Cognito client ID used by command-line API clients."
  value       = aws_cognito_user_pool_client.api.id
}

output "vpc_requests_table_name" {
  description = "DynamoDB table containing VPC requests and progress."
  value       = aws_dynamodb_table.vpc_requests.name
}

output "operations_queue_url" {
  description = "FIFO provisioning queue URL."
  value       = aws_sqs_queue.operations.url
}

output "dead_letter_queue_url" {
  description = "FIFO dead-letter queue URL."
  value       = aws_sqs_queue.dead_letter.url
}
