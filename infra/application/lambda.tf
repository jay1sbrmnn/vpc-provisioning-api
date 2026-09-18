resource "aws_cloudwatch_log_group" "api_lambda" {
  name              = "/aws/lambda/${local.api_function_name}"
  retention_in_days = 14
}

resource "aws_cloudwatch_log_group" "worker_lambda" {
  name              = "/aws/lambda/${local.worker_function_name}"
  retention_in_days = 14
}

resource "aws_lambda_function" "api" {
  function_name    = local.api_function_name
  description      = "Authenticated API for VPC provisioning requests"
  role             = aws_iam_role.api_lambda.arn
  runtime          = "python3.11"
  architectures    = ["x86_64"]
  handler          = "vpc_api.api_lambda_handler.lambda_handler"
  filename         = local.lambda_package
  source_code_hash = filebase64sha256(local.lambda_package)
  timeout          = 15
  memory_size      = 256

  environment {
    variables = {
      QUEUE_URL  = aws_sqs_queue.operations.url
      TABLE_NAME = aws_dynamodb_table.vpc_requests.name
    }
  }

  depends_on = [
    aws_cloudwatch_log_group.api_lambda,
    aws_iam_role_policy.api_lambda,
  ]
}

resource "aws_lambda_function" "worker" {
  function_name    = local.worker_function_name
  description      = "FIFO SQS worker that provisions VPCs and subnets"
  role             = aws_iam_role.worker_lambda.arn
  runtime          = "python3.11"
  architectures    = ["x86_64"]
  handler          = "vpc_api.worker_lambda_handler.lambda_handler"
  filename         = local.lambda_package
  source_code_hash = filebase64sha256(local.lambda_package)
  timeout          = 300
  memory_size      = 512

  environment {
    variables = {
      TABLE_NAME = aws_dynamodb_table.vpc_requests.name
    }
  }

  depends_on = [
    aws_cloudwatch_log_group.worker_lambda,
    aws_iam_role_policy.worker_lambda,
  ]
}

resource "aws_lambda_event_source_mapping" "worker" {
  event_source_arn = aws_sqs_queue.operations.arn
  function_name    = aws_lambda_function.worker.arn
  batch_size       = 1
  enabled          = true

  scaling_config {
    maximum_concurrency = 2
  }
}
