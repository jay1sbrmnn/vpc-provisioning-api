locals {
  name_prefix          = "${var.project_name}-${var.environment}"
  lambda_package       = abspath("${path.module}/../../dist/vpc_api_lambda.zip")
  api_function_name    = "${local.name_prefix}-api"
  worker_function_name = "${local.name_prefix}-worker"

  common_tags = {
    Application = var.project_name
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}
