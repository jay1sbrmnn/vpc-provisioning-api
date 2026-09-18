from __future__ import annotations

import json
import logging
import os
from typing import Any, TypedDict
from uuid import uuid4

import boto3
from botocore.exceptions import ClientError
from pydantic import ValidationError

from vpc_api.dynamodb_repository import VpcItem, VpcRepository
from vpc_api.models import CreateVpcRequest
from vpc_api.validation import validate_vpc_request

logger = logging.getLogger(__name__)


class ApiResponse(TypedDict):
    statusCode: int
    headers: dict[str, str]
    body: str


def lambda_handler(event: dict[str, Any], _context: object) -> ApiResponse:
    route = event.get("routeKey")
    if route not in {"POST /vpcs", "GET /vpcs", "GET /vpcs/{id}"}:
        return error_response(404, "Route not found")

    user_id = _get_authenticated_user_id(event)
    if user_id is None:
        return error_response(401, "Authentication is required")

    region = os.environ["AWS_REGION"]
    table = boto3.resource("dynamodb", region_name=region).Table(os.environ["TABLE_NAME"])
    repository = VpcRepository(table)

    try:
        if route == "GET /vpcs":
            return handle_list_vpcs(repository)
        if route == "GET /vpcs/{id}":
            return handle_get_vpc(event, repository)

        sqs = boto3.client("sqs", region_name=region)
        return handle_create_vpc(
            event,
            user_id,
            repository,
            sqs,
            os.environ["QUEUE_URL"],
            region,
        )
    except ClientError:
        logger.exception("AWS request failed", extra={"route": route})
        return error_response(503, "An AWS service is temporarily unavailable. Please retry.")


def handle_create_vpc(
    event: dict[str, Any],
    user_id: str,
    repository: VpcRepository,
    sqs: Any,
    queue_url: str,
    region: str,
) -> ApiResponse:
    try:
        request = parse_create_request(event.get("body"), region)
    except ValueError as exc:
        return error_response(400, str(exc))

    request_id = f"req-{uuid4()}"
    vpc_request = repository.create_vpc_request(
        request_id=request_id,
        user_id=user_id,
        request=request,
    )

    try:
        sqs.send_message(
            QueueUrl=queue_url,
            MessageBody=json.dumps({"requestId": request_id}),
            MessageGroupId=request_id,
            MessageDeduplicationId=request_id,
        )
    except ClientError:
        logger.exception("Failed to queue VPC creation", extra={"request_id": request_id})
        repository.mark_request_failed(
            request_id,
            error_code="QUEUE_ERROR",
            error_message="The provisioning request could not be queued",
        )
        return error_response(503, "The request could not be queued. Please retry.")

    status_url = f"/vpcs/{request_id}"
    return json_response(
        202,
        {
            "id": request_id,
            "status": vpc_request["status"],
            "statusUrl": status_url,
        },
        location=status_url,
    )


def parse_create_request(body: object, region: str) -> CreateVpcRequest:
    if not isinstance(body, str):
        raise ValueError("Request body must be valid JSON")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise ValueError("Request body must be valid JSON") from None

    try:
        request = CreateVpcRequest.model_validate(payload)
    except ValidationError as error:
        first_error = error.errors(include_url=False)[0]
        field = ".".join(str(part) for part in first_error["loc"])
        message = f"{field}: {first_error['msg']}" if field else first_error["msg"]
        raise ValueError(message) from None

    validate_vpc_request(request, region)
    return request


def handle_get_vpc(
    event: dict[str, Any],
    repository: VpcRepository,
) -> ApiResponse:
    request_id = (event.get("pathParameters") or {}).get("id")
    if not isinstance(request_id, str) or not request_id:
        return error_response(400, "VPC request ID is required")

    vpc_request = repository.get_vpc_request(request_id)
    if vpc_request is None:
        return error_response(404, "VPC request not found")

    return json_response(200, _format_vpc_response(vpc_request, include_subnets=True))


def handle_list_vpcs(repository: VpcRepository) -> ApiResponse:
    vpc_requests = repository.list_vpc_requests()
    return json_response(
        200,
        {"items": [_format_vpc_response(vpc, include_subnets=False) for vpc in vpc_requests]},
    )


def _format_vpc_response(
    vpc_item: VpcItem,
    *,
    include_subnets: bool,
) -> dict[str, object]:
    vpc: dict[str, object] = {
        "id": vpc_item["requestId"],
        "name": vpc_item["name"],
        "vpcCidr": vpc_item["vpcCidr"],
        "awsVpcId": vpc_item.get("awsVpcId"),
        "status": vpc_item["status"],
        "cleanupRequired": vpc_item.get("cleanupRequired", False),
        "createdAt": vpc_item["createdAt"],
        "updatedAt": vpc_item["updatedAt"],
    }
    if include_subnets:
        vpc["subnets"] = vpc_item.get("subnets", [])
    if "errorCode" in vpc_item:
        vpc["errorCode"] = vpc_item["errorCode"]
    if "errorMessage" in vpc_item:
        vpc["errorMessage"] = vpc_item["errorMessage"]
    return vpc


def _get_authenticated_user_id(event: dict[str, Any]) -> str | None:
    try:
        user_id = event["requestContext"]["authorizer"]["jwt"]["claims"]["sub"]
    except (KeyError, TypeError):
        return None
    return user_id if isinstance(user_id, str) and user_id else None


def error_response(status_code: int, message: str) -> ApiResponse:
    return json_response(status_code, {"error": {"message": message}})


def json_response(
    status_code: int,
    body: object,
    location: str | None = None,
) -> ApiResponse:
    headers = {"Content-Type": "application/json"}
    if location:
        headers["Location"] = location

    return {
        "statusCode": status_code,
        "headers": headers,
        "body": json.dumps(body),
    }
