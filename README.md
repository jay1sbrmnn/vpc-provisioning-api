# VPC Provisioning API

A Python API that creates an AWS VPC with 1–10 subnets. Cognito authenticates requests and Terraform deploys the application.

## How it works

```text
Client -> API Gateway -> API Lambda -> DynamoDB
                              |
                              v
                         SQS FIFO -> Worker Lambda -> EC2 API
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

The API validates CIDRs, subnet overlap, names, availability zones, and the subnet count. Request status moves from `PENDING` to `PROVISIONING`, then to `ACTIVE` or `FAILED`.

FIFO ordering keeps work for one request sequential. On retry, the worker resumes the request and uses AWS tags to find resources already created. It removes created resources when a permanent error occurs.

Each successful `POST` creates a new request. Client-controlled idempotency is outside the scope of this exercise; SQS retries remain safe through request status checks and AWS resource tags.

## Assumptions and limits

- Each `POST` provisions one VPC. The API supports multiple POST requests, so it is not limited to one VPC in total.
- The API accepts 1–10 subnets per VPC. One subnet is valid; ten is an application guardrail for a bounded Lambda job and DynamoDB item, not an AWS limit.
- `GET /vpcs` returns the 50 newest requests without pagination. Cursor pagination is deferred because the assessment uses a small dataset.
- All authenticated users have the same access, as requested. Per-user authorization is outside scope.
- Route tables, internet gateways, NAT gateways, and a public delete endpoint are outside scope.

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
