# VPC Provisioning API

A Python API that creates an AWS VPC with 1–10 subnets. Cognito authenticates requests and Terraform deploys the application.

## How it works

```text
Client -> API Gateway -> API Lambda -> DynamoDB
                              |
                              v
                         SQS FIFO -> Worker Lambda -> VPC/Subnet creation
```

VPC creation runs in the worker because it can take longer than an API request. The API returns `202 Accepted`, and the client uses the returned request ID to check progress.

## API

All routes require a Cognito bearer token.

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/vpcs` | Create a VPC and subnets. |
| `GET` | `/vpcs` | List VPC requests. |
| `GET` | `/vpcs/{id}` | Get one request and its subnets. |

`GET /vpcs` returns the 50 most recent requests. Cursor pagination would be added for production-scale usage.

### Sample `POST /vpcs` request

```json
{
  "name": "demo-network",
  "vpcCidr": "10.0.0.0/16",
  "subnets": [
    {
      "name": "subnet-a",
      "cidr": "10.0.1.0/24",
      "availabilityZone": "ap-south-1a"
    },
    {
      "name": "subnet-b",
      "cidr": "10.0.2.0/24",
      "availabilityZone": "ap-south-1b"
    }
  ]
}
```

### Create VPC flow

1. API Gateway verifies the Cognito JWT and applies stage throttling before invoking the API Lambda.
2. The API Lambda validates the JSON shape, names, CIDRs, subnet count, subnet relationships, and availability-zone naming format.
3. DynamoDB stores one `PENDING` VPC request item containing the requested subnets.
4. The API Lambda sends only the `requestId` to FIFO SQS, using it as both the message group and deduplication ID, then returns `202 Accepted`.
5. The worker conditionally changes a `PENDING` request to `PROVISIONING`, or resumes one already in `PROVISIONING`; requests already `ACTIVE` or `FAILED` are skipped.
6. It finds or creates the tagged VPC, then finds or creates each tagged subnet sequentially.
7. VPC and subnet IDs and progress are saved after each completed creation so retries can resume safely.
8. The request becomes `ACTIVE` after every subnet is active.

Each successful `POST` creates a new request. Client-controlled idempotency is outside the scope of this exercise; SQS retries remain safe through request status checks and AWS resource tags.

## Assumptions and limits

- Each `POST` provisions one VPC. The API supports multiple POST requests, so it is not limited to one VPC in total.
- The API accepts 1–10 subnets per VPC. One subnet is valid; the upper limit keeps sequential provisioning, progress storage, and rollback bounded within one worker job.
- `GET /vpcs` returns the 50 newest requests without pagination to keep the query and response bounded. Cursor pagination is deferred because the assessment uses a small dataset.
- VPC CIDRs are not checked for overlap across separate requests because AWS permits isolated VPCs to use overlapping ranges.
- Availability zones are checked for the configured region's naming format, but not for existence or account availability. EC2 rejects an unavailable zone during provisioning; the request is marked `FAILED`, and the worker deletes any VPC and subnets already created. If cleanup cannot finish, `cleanupRequired` is recorded for manual action.
- All authenticated users have the same access, as requested. Per-user authorization is outside scope.
- Route tables, internet gateways, NAT gateways, and a public delete endpoint are outside scope.

## Failure, retry, and rollback

- If the API cannot queue a request, it marks the DynamoDB record `FAILED` and returns an error without creating AWS network resources.
- The worker raises retryable AWS errors and DynamoDB progress-write failures so SQS can invoke it again. Saved progress and AWS tags let retries resume and find resources already created; after three failed receives, SQS moves the message to the dead-letter queue.
- For a permanent provisioning error, the worker deletes created subnets in reverse order and then deletes the VPC before marking the request `FAILED`. If any deletion fails, it sets `cleanupRequired` for manual cleanup.

## Local checks

Install [uv](https://docs.astral.sh/uv/), then run:

```bash
uv python install 3.11
uv sync --frozen
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy
```

## Deploy

See [infra/application/README.md](infra/application/README.md).

The Terraform state is stored locally and ignored by Git. Keep the state file while the application is deployed. Delete test VPCs before running `terraform destroy`.
