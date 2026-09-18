#!/usr/bin/env bash

set -euo pipefail

if [[ -z "${API_URL:-}" || -z "${ID_TOKEN:-}" ]]; then
  echo "Set API_URL and ID_TOKEN before running this script."
  exit 1
fi

API_URL="${API_URL%/}"
REGION="${AWS_REGION:-ap-south-1}"

work_dir="$(mktemp -d)"
trap 'rm -rf "$work_dir"' EXIT

create_file="$work_dir/create.json"
status_file="$work_dir/status.json"
list_file="$work_dir/list.json"

json_value() {
  python3 - "$1" "$2" <<'PYTHON'
import json
import sys

with open(sys.argv[1]) as file:
    print(json.load(file)[sys.argv[2]])
PYTHON
}

echo "This will create a VPC and two subnets in $REGION."
read -r -p "Continue? [y/N] " answer
[[ "$answer" =~ ^[Yy]$ ]] || exit 0

echo
echo "Creating VPC..."
http_status="$(curl -sS -o "$create_file" -w "%{http_code}" \
  -X POST "$API_URL/vpcs" \
  -H "Authorization: Bearer $ID_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"name\": \"smoke-test-vpc\",
    \"vpcCidr\": \"10.50.0.0/16\",
    \"subnets\": [
      {
        \"name\": \"public-a\",
        \"cidr\": \"10.50.1.0/24\",
        \"availabilityZone\": \"${REGION}a\"
      },
      {
        \"name\": \"private-b\",
        \"cidr\": \"10.50.2.0/24\",
        \"availabilityZone\": \"${REGION}b\"
      }
    ]
  }")"

python3 -m json.tool "$create_file" || cat "$create_file"

if [[ "$http_status" != "202" ]]; then
  echo "POST /vpcs returned HTTP $http_status"
  exit 1
fi

request_id="$(json_value "$create_file" "id")"

echo
echo "Waiting for $request_id to finish..."

status=""
for _ in {1..60}; do
  sleep 5

  http_status="$(curl -sS -o "$status_file" -w "%{http_code}" \
    "$API_URL/vpcs/$request_id" \
    -H "Authorization: Bearer $ID_TOKEN")"

  if [[ "$http_status" != "200" ]]; then
    echo "GET /vpcs/$request_id returned HTTP $http_status"
    cat "$status_file"
    exit 1
  fi

  status="$(json_value "$status_file" "status")"
  echo "Status: $status"

  [[ "$status" == "ACTIVE" || "$status" == "FAILED" ]] && break
done

echo
python3 -m json.tool "$status_file"

if [[ "$status" != "ACTIVE" ]]; then
  echo "VPC provisioning did not complete successfully."
  exit 1
fi

echo
echo "Checking GET /vpcs..."
curl -fsS "$API_URL/vpcs" \
  -H "Authorization: Bearer $ID_TOKEN" \
  -o "$list_file"

python3 -m json.tool "$list_file"

python3 - "$list_file" "$request_id" <<'PYTHON'
import json
import sys

with open(sys.argv[1]) as file:
    response = json.load(file)

request_id = sys.argv[2]
if not any(item["id"] == request_id for item in response["items"]):
    raise SystemExit(f"{request_id} was not returned by GET /vpcs")

print(f"GET /vpcs returned {request_id}.")
PYTHON

echo
read -r -p "Delete the test VPC and subnets? [y/N] " answer
if [[ ! "$answer" =~ ^[Yy]$ ]]; then
  echo "Cleanup skipped. VPC ID: $(json_value "$status_file" "awsVpcId")"
  exit 0
fi

python3 - "$status_file" <<'PYTHON' | while read -r subnet_id; do
import json
import sys

with open(sys.argv[1]) as file:
    response = json.load(file)

for subnet in response["subnets"]:
    print(subnet["awsSubnetId"])
PYTHON
  echo "Deleting subnet $subnet_id..."
  aws ec2 delete-subnet --subnet-id "$subnet_id" --region "$REGION"
done

vpc_id="$(json_value "$status_file" "awsVpcId")"
echo "Deleting VPC $vpc_id..."
aws ec2 delete-vpc --vpc-id "$vpc_id" --region "$REGION"

echo "Cleanup complete. The DynamoDB request record remains as test history."
