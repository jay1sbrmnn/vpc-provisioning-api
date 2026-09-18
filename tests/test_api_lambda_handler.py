import json
from typing import Any
from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from vpc_api.api_lambda_handler import handle_create_vpc


def api_event() -> dict[str, Any]:
    return {
        "body": json.dumps(
            {
                "name": "demo-vpc",
                "vpcCidr": "10.0.0.0/16",
                "subnets": [
                    {
                        "name": "application",
                        "cidr": "10.0.1.0/24",
                        "availabilityZone": "ap-south-1a",
                    },
                    {
                        "name": "database",
                        "cidr": "10.0.2.0/24",
                        "availabilityZone": "ap-south-1b",
                    },
                ],
            }
        )
    }


@patch("vpc_api.api_lambda_handler.uuid4", return_value="fixed")
def test_queue_failure_marks_the_saved_request_failed(_uuid: MagicMock) -> None:
    repository = MagicMock()
    repository.create_vpc_request.return_value = {
        "requestId": "req-fixed",
        "status": "PENDING",
    }
    sqs = MagicMock()
    sqs.send_message.side_effect = ClientError(
        {"Error": {"Code": "ServiceUnavailable", "Message": "try again"}},
        "SendMessage",
    )

    response = handle_create_vpc(
        api_event(), "user-123", repository, sqs, "queue-url", "ap-south-1"
    )

    assert response["statusCode"] == 503
    repository.mark_request_failed.assert_called_once_with(
        "req-fixed",
        error_code="QUEUE_ERROR",
        error_message="The provisioning request could not be queued",
    )
