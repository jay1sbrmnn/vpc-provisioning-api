from __future__ import annotations

from typing import Any

from vpc_api.dynamodb_repository import SubnetItem, VpcItem

MANAGED_BY = "vpc-provisioning-api"


class AwsNetwork:
    def __init__(self, ec2: Any) -> None:
        self.ec2 = ec2

    def find_or_create_vpc(self, vpc_request: VpcItem) -> str:
        existing_id = vpc_request.get("awsVpcId")
        if existing_id:
            return existing_id

        request_id = vpc_request["requestId"]
        describe_response = self.ec2.describe_vpcs(
            Filters=[
                {"Name": "tag:ManagedBy", "Values": [MANAGED_BY]},
                {"Name": "tag:ProvisioningRequestId", "Values": [request_id]},
            ]
        )
        existing_vpcs = describe_response.get("Vpcs", [])
        if existing_vpcs:
            vpc_id = existing_vpcs[0].get("VpcId")
            if isinstance(vpc_id, str):
                return vpc_id

        tag_specification = {
            "ResourceType": "vpc",
            "Tags": self._build_resource_tags(request_id, vpc_request["name"]),
        }
        create_response = self.ec2.create_vpc(
            CidrBlock=vpc_request["vpcCidr"],
            TagSpecifications=[tag_specification],
        )
        vpc_id = create_response.get("Vpc", {}).get("VpcId")
        if not isinstance(vpc_id, str):
            raise RuntimeError("AWS created a VPC without returning its ID")
        self.ec2.get_waiter("vpc_available").wait(VpcIds=[vpc_id])
        return vpc_id

    def find_or_create_subnet(
        self,
        vpc_request: VpcItem,
        subnet: SubnetItem,
    ) -> str:
        existing_id = subnet.get("awsSubnetId")
        if existing_id:
            return existing_id

        request_id = vpc_request["requestId"]
        subnet_id = subnet["subnetId"]
        aws_vpc_id = vpc_request.get("awsVpcId")
        if not aws_vpc_id:
            raise RuntimeError("A subnet cannot be created before its VPC")

        describe_response = self.ec2.describe_subnets(
            Filters=[
                {"Name": "vpc-id", "Values": [aws_vpc_id]},
                {"Name": "tag:ManagedBy", "Values": [MANAGED_BY]},
                {"Name": "tag:ProvisioningRequestId", "Values": [request_id]},
                {"Name": "tag:ProvisioningSubnetId", "Values": [subnet_id]},
            ]
        )
        existing_subnets = describe_response.get("Subnets", [])
        if existing_subnets:
            aws_subnet_id = existing_subnets[0].get("SubnetId")
            if isinstance(aws_subnet_id, str):
                return aws_subnet_id

        tag_specification = {
            "ResourceType": "subnet",
            "Tags": self._build_resource_tags(request_id, subnet["name"], subnet_id),
        }
        create_response = self.ec2.create_subnet(
            VpcId=aws_vpc_id,
            CidrBlock=subnet["cidr"],
            AvailabilityZone=subnet["availabilityZone"],
            TagSpecifications=[tag_specification],
        )
        aws_subnet_id = create_response.get("Subnet", {}).get("SubnetId")
        if not isinstance(aws_subnet_id, str):
            raise RuntimeError("AWS created a subnet without returning its ID")
        return aws_subnet_id

    def delete_subnet(self, subnet_id: str) -> None:
        self.ec2.delete_subnet(SubnetId=subnet_id)

    def delete_vpc(self, vpc_id: str) -> None:
        self.ec2.delete_vpc(VpcId=vpc_id)

    @staticmethod
    def _build_resource_tags(
        request_id: str,
        name: str,
        subnet_id: str | None = None,
    ) -> list[dict[str, str]]:
        tags = [
            {"Key": "ManagedBy", "Value": MANAGED_BY},
            {"Key": "ProvisioningRequestId", "Value": request_id},
            {"Key": "Name", "Value": name},
        ]
        if subnet_id:
            tags.append({"Key": "ProvisioningSubnetId", "Value": subnet_id})
        return tags
