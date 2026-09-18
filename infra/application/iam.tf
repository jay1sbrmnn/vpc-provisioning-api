data "aws_iam_policy_document" "lambda_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "api_lambda" {
  name               = "${local.name_prefix}-api-lambda"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

resource "aws_iam_role" "worker_lambda" {
  name               = "${local.name_prefix}-worker-lambda"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

data "aws_iam_policy_document" "api_lambda" {
  statement {
    sid = "WriteFunctionLogs"
    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]
    resources = ["${aws_cloudwatch_log_group.api_lambda.arn}:*"]
  }

  statement {
    sid = "UseVpcRequestTable"
    actions = [
      "dynamodb:GetItem",
      "dynamodb:PutItem",
      "dynamodb:Query",
      "dynamodb:UpdateItem",
    ]
    resources = [
      aws_dynamodb_table.vpc_requests.arn,
      "${aws_dynamodb_table.vpc_requests.arn}/index/*",
    ]
  }

  statement {
    sid       = "QueueProvisioningOperations"
    actions   = ["sqs:SendMessage"]
    resources = [aws_sqs_queue.operations.arn]
  }
}

resource "aws_iam_role_policy" "api_lambda" {
  name   = "${local.name_prefix}-api-lambda"
  role   = aws_iam_role.api_lambda.id
  policy = data.aws_iam_policy_document.api_lambda.json
}

data "aws_iam_policy_document" "worker_lambda" {
  statement {
    sid = "WriteFunctionLogs"
    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]
    resources = ["${aws_cloudwatch_log_group.worker_lambda.arn}:*"]
  }

  statement {
    sid = "UpdateVpcRequests"
    actions = [
      "dynamodb:PutItem",
      "dynamodb:UpdateItem",
    ]
    resources = [aws_dynamodb_table.vpc_requests.arn]
  }

  statement {
    sid = "ConsumeProvisioningOperations"
    actions = [
      "sqs:ChangeMessageVisibility",
      "sqs:DeleteMessage",
      "sqs:GetQueueAttributes",
      "sqs:ReceiveMessage",
    ]
    resources = [aws_sqs_queue.operations.arn]
  }

  statement {
    sid = "DescribeManagedNetworks"
    actions = [
      "ec2:DescribeSubnets",
      "ec2:DescribeVpcs",
    ]
    resources = ["*"]
  }

  statement {
    sid       = "CreateManagedVpcs"
    actions   = ["ec2:CreateVpc"]
    resources = ["arn:aws:ec2:${var.aws_region}:*:vpc/*"]

    condition {
      test     = "StringEquals"
      variable = "aws:RequestTag/ManagedBy"
      values   = ["vpc-provisioning-api"]
    }
  }

  statement {
    sid       = "CreateManagedSubnets"
    actions   = ["ec2:CreateSubnet"]
    resources = ["arn:aws:ec2:${var.aws_region}:*:subnet/*"]

    condition {
      test     = "StringEquals"
      variable = "aws:RequestTag/ManagedBy"
      values   = ["vpc-provisioning-api"]
    }
  }

  statement {
    sid       = "CreateSubnetsInManagedVpcs"
    actions   = ["ec2:CreateSubnet"]
    resources = ["arn:aws:ec2:${var.aws_region}:*:vpc/*"]

    condition {
      test     = "StringEquals"
      variable = "ec2:ResourceTag/ManagedBy"
      values   = ["vpc-provisioning-api"]
    }
  }

  statement {
    sid       = "TagNetworksDuringCreation"
    actions   = ["ec2:CreateTags"]
    resources = ["*"]

    condition {
      test     = "StringEquals"
      variable = "ec2:CreateAction"
      values   = ["CreateSubnet", "CreateVpc"]
    }
  }

  statement {
    sid = "DeleteManagedNetworks"
    actions = [
      "ec2:DeleteSubnet",
      "ec2:DeleteVpc",
    ]
    resources = ["*"]

    condition {
      test     = "StringEquals"
      variable = "ec2:ResourceTag/ManagedBy"
      values   = ["vpc-provisioning-api"]
    }
  }
}

resource "aws_iam_role_policy" "worker_lambda" {
  name   = "${local.name_prefix}-worker-lambda"
  role   = aws_iam_role.worker_lambda.id
  policy = data.aws_iam_policy_document.worker_lambda.json
}
