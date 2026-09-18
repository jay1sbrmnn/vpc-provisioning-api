resource "aws_apigatewayv2_api" "vpc" {
  name          = "${local.name_prefix}-http-api"
  protocol_type = "HTTP"
}

resource "aws_apigatewayv2_authorizer" "cognito" {
  api_id           = aws_apigatewayv2_api.vpc.id
  authorizer_type  = "JWT"
  identity_sources = ["$request.header.Authorization"]
  name             = "cognito"

  jwt_configuration {
    audience = [aws_cognito_user_pool_client.api.id]
    issuer   = "https://cognito-idp.${var.aws_region}.amazonaws.com/${aws_cognito_user_pool.api.id}"
  }
}

resource "aws_apigatewayv2_integration" "api_lambda" {
  api_id                 = aws_apigatewayv2_api.vpc.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.api.invoke_arn
  integration_method     = "POST"
  payload_format_version = "2.0"
  timeout_milliseconds   = 29000
}

locals {
  implemented_routes = toset([
    "GET /vpcs",
    "GET /vpcs/{id}",
    "POST /vpcs",
  ])
}

resource "aws_apigatewayv2_route" "vpc" {
  for_each = local.implemented_routes

  api_id             = aws_apigatewayv2_api.vpc.id
  route_key          = each.value
  target             = "integrations/${aws_apigatewayv2_integration.api_lambda.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito.id
}

resource "aws_cloudwatch_log_group" "api_gateway" {
  name              = "/aws/apigateway/${local.name_prefix}"
  retention_in_days = 14
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.vpc.id
  name        = "$default"
  auto_deploy = true

  default_route_settings {
    throttling_burst_limit = 20
    throttling_rate_limit  = 10
  }

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_gateway.arn
    format = jsonencode({
      requestId        = "$context.requestId"
      requestTime      = "$context.requestTime"
      routeKey         = "$context.routeKey"
      status           = "$context.status"
      responseLength   = "$context.responseLength"
      integrationError = "$context.integrationErrorMessage"
    })
  }

  depends_on = [aws_apigatewayv2_route.vpc]
}

resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowApiGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.vpc.execution_arn}/*/*"
}
