from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, NotRequired, TypedDict

from boto3.dynamodb.conditions import Key

from vpc_api.models import CreateVpcRequest


class SubnetItem(TypedDict):
    subnetId: str
    name: str
    cidr: str
    availabilityZone: str
    awsSubnetId: str | None
    status: str
    createdAt: str
    updatedAt: str


class VpcItem(TypedDict):
    requestId: str
    itemType: str
    name: str
    vpcCidr: str
    awsVpcId: str | None
    status: str
    requestedBy: str
    cleanupRequired: bool
    createdAt: str
    updatedAt: str
    subnets: list[SubnetItem]
    errorCode: NotRequired[str]
    errorMessage: NotRequired[str]


class VpcRepository:
    def __init__(self, table: Any) -> None:
        self.table = table

    def create_vpc_request(
        self,
        request_id: str,
        user_id: str,
        request: CreateVpcRequest,
    ) -> VpcItem:
        now = datetime.now(UTC).isoformat()

        subnets: list[SubnetItem] = []
        sorted_subnets = sorted(request.subnets, key=lambda subnet: subnet.name)
        for number, subnet in enumerate(sorted_subnets, start=1):
            subnets.append(
                {
                    "subnetId": f"subnet-{number}",
                    "name": subnet.name,
                    "cidr": subnet.cidr,
                    "availabilityZone": subnet.availability_zone,
                    "awsSubnetId": None,
                    "status": "PENDING",
                    "createdAt": now,
                    "updatedAt": now,
                }
            )

        vpc_item: VpcItem = {
            "requestId": request_id,
            "itemType": "VPC",
            "name": request.name,
            "vpcCidr": request.vpc_cidr,
            "awsVpcId": None,
            "status": "PENDING",
            "requestedBy": user_id,
            "cleanupRequired": False,
            "createdAt": now,
            "updatedAt": now,
            "subnets": subnets,
        }

        self.table.put_item(
            Item=vpc_item,
            ConditionExpression="attribute_not_exists(requestId)",
        )
        return vpc_item

    def get_vpc_request(self, request_id: str) -> VpcItem | None:
        response = self.table.get_item(
            Key={"requestId": request_id},
            ConsistentRead=True,
        )
        vpc_item: VpcItem | None = response.get("Item")
        return vpc_item

    def mark_request_failed(
        self,
        request_id: str,
        error_code: str,
        error_message: str,
    ) -> None:
        now = datetime.now(UTC).isoformat()
        self.table.update_item(
            Key={"requestId": request_id},
            UpdateExpression=(
                "SET #status = :failed, errorCode = :error_code, "
                "errorMessage = :error_message, updatedAt = :now"
            ),
            ConditionExpression="#status = :pending",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":pending": "PENDING",
                ":failed": "FAILED",
                ":error_code": error_code,
                ":error_message": error_message,
                ":now": now,
            },
        )

    def list_vpc_requests(self, limit: int = 50) -> list[VpcItem]:
        response = self.table.query(
            IndexName="VpcListIndex",
            KeyConditionExpression=Key("itemType").eq("VPC"),
            ScanIndexForward=False,
            Limit=limit,
        )
        items: list[VpcItem] = response.get("Items", [])
        return items

    def start_or_resume_vpc_creation(self, request_id: str) -> VpcItem:
        condition = "#status = :pending OR #status = :provisioning"
        values = {
            ":pending": "PENDING",
            ":provisioning": "PROVISIONING",
            ":now": datetime.now(UTC).isoformat(),
        }

        response = self.table.update_item(
            Key={"requestId": request_id},
            UpdateExpression="SET #status = :provisioning, updatedAt = :now",
            ConditionExpression=condition,
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues=values,
            ReturnValues="ALL_NEW",
        )
        vpc_request: VpcItem = response["Attributes"]
        return vpc_request

    def save_provisioning_progress(self, vpc_request: VpcItem) -> None:
        vpc_request["updatedAt"] = datetime.now(UTC).isoformat()
        self.table.put_item(
            Item=vpc_request,
            ConditionExpression="attribute_exists(requestId)",
        )
