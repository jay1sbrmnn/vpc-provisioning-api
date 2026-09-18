import pytest

from vpc_api.models import CreateVpcRequest
from vpc_api.validation import validate_vpc_request


def valid_request() -> CreateVpcRequest:
    return CreateVpcRequest.model_validate(
        {
            "name": "demo-vpc",
            "vpcCidr": "10.20.0.0/16",
            "subnets": [
                {
                    "name": "application-a",
                    "cidr": "10.20.3.0/24",
                    "availabilityZone": "ap-south-1a",
                },
                {
                    "name": "database-b",
                    "cidr": "10.20.19.0/24",
                    "availabilityZone": "ap-south-1b",
                },
            ],
        }
    )


def test_accepts_a_valid_request() -> None:
    validate_vpc_request(valid_request(), "ap-south-1")

    request = valid_request()
    one_subnet_request = CreateVpcRequest.model_validate(
        {
            "name": request.name,
            "vpcCidr": request.vpc_cidr,
            "subnets": [request.subnets[0].model_dump(by_alias=True)],
        }
    )
    validate_vpc_request(one_subnet_request, "ap-south-1")


def test_rejects_invalid_vpc_cidr() -> None:
    request = valid_request()
    request.vpc_cidr = "10.20.0.1/16"

    with pytest.raises(ValueError, match="VPC CIDR"):
        validate_vpc_request(request, "ap-south-1")


def test_rejects_subnet_outside_vpc() -> None:
    request = valid_request()
    request.subnets[1].cidr = "10.21.0.0/24"

    with pytest.raises(ValueError, match="outside VPC"):
        validate_vpc_request(request, "ap-south-1")


def test_rejects_overlapping_subnets() -> None:
    request = valid_request()
    request.subnets[1].cidr = "10.20.2.0/23"

    with pytest.raises(ValueError, match="must not overlap"):
        validate_vpc_request(request, "ap-south-1")


def test_rejects_availability_zone_from_another_region() -> None:
    request = valid_request()
    request.subnets[1].availability_zone = "eu-west-1b"

    with pytest.raises(ValueError, match="does not belong"):
        validate_vpc_request(request, "ap-south-1")
