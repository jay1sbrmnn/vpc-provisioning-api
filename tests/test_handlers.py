import json

import pytest

from vpc_api.worker_lambda_handler import parse_message


def test_worker_message_contains_only_the_request_id() -> None:
    assert parse_message(json.dumps({"requestId": "req-123"})) == {"requestId": "req-123"}


def test_worker_message_requires_a_request_id() -> None:
    with pytest.raises(ValueError, match="SQS message is invalid"):
        parse_message("{}")
