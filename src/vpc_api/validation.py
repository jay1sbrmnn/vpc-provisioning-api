"""Validation for VPC creation requests."""

import re
from ipaddress import IPv4Network, ip_network

from vpc_api.models import CreateVpcRequest


def validate_vpc_request(request: CreateVpcRequest, region: str) -> None:
    if not region:
        raise ValueError("AWS region is required")

    vpc_network = _parse_cidr(request.vpc_cidr, "VPC CIDR")
    zone_pattern = re.compile(rf"^{re.escape(region)}[a-z]$")
    subnet_names: set[str] = set()
    subnet_networks: list[IPv4Network] = []

    for subnet in request.subnets:
        name = subnet.name.casefold()
        if name in subnet_names:
            raise ValueError("Subnet names must be unique")
        subnet_names.add(name)

        if zone_pattern.fullmatch(subnet.availability_zone) is None:
            raise ValueError(
                f"Availability zone {subnet.availability_zone} does not belong to {region}"
            )

        network = _parse_cidr(subnet.cidr, "Subnet CIDR")
        if not network.subnet_of(vpc_network):
            raise ValueError(f"Subnet {subnet.cidr} is outside VPC {request.vpc_cidr}")

        if any(network.overlaps(existing) for existing in subnet_networks):
            raise ValueError("Subnet CIDR blocks must not overlap")

        subnet_networks.append(network)


def _parse_cidr(value: str, label: str) -> IPv4Network:
    try:
        network = ip_network(value, strict=True)
    except ValueError:
        raise ValueError(f"{label} must be a valid network address") from None

    if not isinstance(network, IPv4Network) or not 16 <= network.prefixlen <= 28:
        raise ValueError(f"{label} must be an IPv4 network between /16 and /28")

    return network
