resource "aws_dynamodb_table" "vpc_requests" {
  name         = "${local.name_prefix}-vpc-requests"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "requestId"

  attribute {
    name = "requestId"
    type = "S"
  }

  attribute {
    name = "itemType"
    type = "S"
  }

  attribute {
    name = "createdAt"
    type = "S"
  }

  global_secondary_index {
    name            = "VpcListIndex"
    hash_key        = "itemType"
    range_key       = "createdAt"
    projection_type = "ALL"
  }

  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled = true
  }
}
