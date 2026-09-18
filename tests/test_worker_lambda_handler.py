from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from vpc_api.dynamodb_repository import VpcItem
from vpc_api.worker_lambda_handler import process_vpc_creation


def provisioning_request() -> VpcItem:
    return {
        "requestId": "req-123",
        "itemType": "VPC",
        "name": "demo-vpc",
        "vpcCidr": "10.0.0.0/16",
        "awsVpcId": None,
        "status": "PROVISIONING",
        "requestedBy": "user-123",
        "cleanupRequired": False,
        "createdAt": "2026-09-17T10:00:00+00:00",
        "updatedAt": "2026-09-17T10:00:00+00:00",
        "subnets": [
            {
                "subnetId": "subnet-1",
                "name": "application",
                "cidr": "10.0.1.0/24",
                "availabilityZone": "ap-south-1a",
                "awsSubnetId": None,
                "status": "PENDING",
                "createdAt": "2026-09-17T10:00:00+00:00",
                "updatedAt": "2026-09-17T10:00:00+00:00",
            },
            {
                "subnetId": "subnet-2",
                "name": "database",
                "cidr": "10.0.2.0/24",
                "availabilityZone": "ap-south-1b",
                "awsSubnetId": None,
                "status": "PENDING",
                "createdAt": "2026-09-17T10:00:00+00:00",
                "updatedAt": "2026-09-17T10:00:00+00:00",
            },
        ],
    }


def client_error(code: str, operation: str = "CreateSubnet") -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": "failed"}}, operation)


@patch("vpc_api.worker_lambda_handler.AwsNetwork")
def test_terminal_error_rolls_back_created_resources(network_class: MagicMock) -> None:
    repository = MagicMock()
    vpc = provisioning_request()
    repository.start_or_resume_vpc_creation.return_value = vpc
    network = network_class.return_value
    network.find_or_create_vpc.return_value = "vpc-123"
    network.find_or_create_subnet.side_effect = [
        "subnet-a",
        client_error("InvalidSubnet.Conflict"),
    ]

    process_vpc_creation({"requestId": "req-123"}, repository, MagicMock())

    network.delete_subnet.assert_called_once_with("subnet-a")
    network.delete_vpc.assert_called_once_with("vpc-123")
    assert vpc["status"] == "FAILED"
    assert vpc["cleanupRequired"] is False
    assert vpc["errorCode"] == "InvalidSubnet.Conflict"


@patch("vpc_api.worker_lambda_handler.AwsNetwork")
def test_rollback_failure_is_recorded_for_manual_cleanup(network_class: MagicMock) -> None:
    repository = MagicMock()
    vpc = provisioning_request()
    repository.start_or_resume_vpc_creation.return_value = vpc
    network = network_class.return_value
    network.find_or_create_vpc.return_value = "vpc-123"
    network.find_or_create_subnet.side_effect = [
        "subnet-a",
        client_error("InvalidSubnet.Conflict"),
    ]
    network.delete_subnet.side_effect = client_error("DependencyViolation", "DeleteSubnet")

    process_vpc_creation({"requestId": "req-123"}, repository, MagicMock())

    assert vpc["status"] == "FAILED"
    assert vpc["cleanupRequired"] is True


@patch("vpc_api.worker_lambda_handler.AwsNetwork")
def test_retryable_aws_error_is_raised_for_sqs_to_retry(network_class: MagicMock) -> None:
    repository = MagicMock()
    repository.start_or_resume_vpc_creation.return_value = provisioning_request()
    network_class.return_value.find_or_create_vpc.side_effect = client_error("Throttling")

    with pytest.raises(ClientError):
        process_vpc_creation({"requestId": "req-123"}, repository, MagicMock())

    repository.save_provisioning_progress.assert_not_called()
