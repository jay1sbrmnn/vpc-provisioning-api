from __future__ import annotations

import json
import logging
import os
from typing import Any

import boto3
from botocore.exceptions import ClientError

from vpc_api.aws_helper import AwsNetwork
from vpc_api.dynamodb_repository import VpcItem, VpcRepository

logger = logging.getLogger(__name__)

RETRYABLE_AWS_ERRORS = {
    "InternalError",
    "InternalServerError",
    "ProvisionedThroughputExceededException",
    "RequestLimitExceeded",
    "RequestTimeout",
    "ServiceUnavailable",
    "Throttling",
    "ThrottlingException",
}


def lambda_handler(event: dict[str, Any], _context: object) -> None:
    region = os.environ["AWS_REGION"]
    table = boto3.resource("dynamodb", region_name=region).Table(os.environ["TABLE_NAME"])
    repository = VpcRepository(table)
    ec2 = boto3.client("ec2", region_name=region)

    for record in event["Records"]:
        message = parse_message(record["body"])
        process_vpc_creation(message, repository, ec2)


def parse_message(body: str) -> dict[str, str]:
    try:
        message = json.loads(body)
        request_id = message["requestId"]
    except (json.JSONDecodeError, KeyError, TypeError):
        raise ValueError("SQS message is invalid") from None

    if not isinstance(request_id, str) or not request_id:
        raise ValueError("SQS message has no requestId")

    return {"requestId": request_id}


def process_vpc_creation(
    message: dict[str, str],
    repository: VpcRepository,
    ec2: Any,
) -> None:
    vpc_request = _start_or_resume_request(message["requestId"], repository)
    if vpc_request is None:
        return

    network = AwsNetwork(ec2)
    try:
        provision_vpc(vpc_request, repository, network)
    except ClientError as error:
        error_code = error.response.get("Error", {}).get("Code", "AWS_ERROR")
        logger.exception("VPC provisioning failed", extra={"request_id": message["requestId"]})

        if error.operation_name == "PutItem" or error_code in RETRYABLE_AWS_ERRORS:
            raise

        _rollback_failed_provisioning(vpc_request, repository, network, error_code)


def _start_or_resume_request(
    request_id: str,
    repository: VpcRepository,
) -> VpcItem | None:
    try:
        return repository.start_or_resume_vpc_creation(request_id)
    except ClientError as error:
        error_code = error.response.get("Error", {}).get("Code")
        if error_code != "ConditionalCheckFailedException":
            raise
        return None


def provision_vpc(
    vpc_request: VpcItem,
    repository: VpcRepository,
    network: AwsNetwork,
) -> None:
    vpc_request["awsVpcId"] = network.find_or_create_vpc(vpc_request)
    repository.save_provisioning_progress(vpc_request)

    for subnet in vpc_request["subnets"]:
        if subnet["status"] == "ACTIVE" and subnet.get("awsSubnetId"):
            continue

        subnet["status"] = "CREATING"
        repository.save_provisioning_progress(vpc_request)

        subnet["awsSubnetId"] = network.find_or_create_subnet(vpc_request, subnet)
        subnet["status"] = "ACTIVE"
        repository.save_provisioning_progress(vpc_request)

    vpc_request["status"] = "ACTIVE"
    vpc_request["cleanupRequired"] = False
    vpc_request.pop("errorCode", None)
    vpc_request.pop("errorMessage", None)
    repository.save_provisioning_progress(vpc_request)


def _rollback_failed_provisioning(
    vpc_request: VpcItem,
    repository: VpcRepository,
    network: AwsNetwork,
    error_code: str,
) -> None:
    cleanup_required = False

    for subnet in reversed(vpc_request["subnets"]):
        aws_subnet_id = subnet.get("awsSubnetId")
        if aws_subnet_id:
            try:
                network.delete_subnet(aws_subnet_id)
                subnet["awsSubnetId"] = None
            except ClientError:
                cleanup_required = True
        subnet["status"] = "FAILED"

    aws_vpc_id = vpc_request.get("awsVpcId")
    if aws_vpc_id:
        try:
            network.delete_vpc(aws_vpc_id)
            vpc_request["awsVpcId"] = None
        except ClientError:
            cleanup_required = True

    vpc_request["status"] = "FAILED"
    vpc_request["cleanupRequired"] = cleanup_required
    vpc_request["errorCode"] = error_code
    vpc_request["errorMessage"] = "AWS could not provision the requested network"
    repository.save_provisioning_progress(vpc_request)
