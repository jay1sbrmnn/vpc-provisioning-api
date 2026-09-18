from pydantic import BaseModel, ConfigDict, Field

RESOURCE_NAME_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$"


class SubnetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=64, pattern=RESOURCE_NAME_PATTERN)
    cidr: str = Field(min_length=1)
    availability_zone: str = Field(alias="availabilityZone", min_length=1)


class CreateVpcRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=64, pattern=RESOURCE_NAME_PATTERN)
    vpc_cidr: str = Field(alias="vpcCidr", min_length=1)
    subnets: list[SubnetRequest] = Field(min_length=1, max_length=10)
