resource "aws_sqs_queue" "dead_letter" {
  name                        = "${local.name_prefix}-operations-dlq.fifo"
  fifo_queue                  = true
  content_based_deduplication = false
  message_retention_seconds   = 1209600
  sqs_managed_sse_enabled     = true
}

resource "aws_sqs_queue" "operations" {
  name                        = "${local.name_prefix}-operations.fifo"
  fifo_queue                  = true
  content_based_deduplication = false
  receive_wait_time_seconds   = 20
  visibility_timeout_seconds  = 1800
  message_retention_seconds   = 345600
  sqs_managed_sse_enabled     = true

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dead_letter.arn
    maxReceiveCount     = 3
  })
}

resource "aws_sqs_queue_redrive_allow_policy" "dead_letter" {
  queue_url = aws_sqs_queue.dead_letter.id

  redrive_allow_policy = jsonencode({
    redrivePermission = "byQueue"
    sourceQueueArns   = [aws_sqs_queue.operations.arn]
  })
}
