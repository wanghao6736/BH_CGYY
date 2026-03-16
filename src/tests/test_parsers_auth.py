from src.parsers.auth import parse_auth_token_response


def test_parse_auth_token_response_extracts_access_token_and_roles() -> None:
    resp = {
        "code": 200,
        "data": {
            "token": {
                "access_token": "abc123",
            },
            "roles": [
                {"id": 3, "name": "学生", "roleType": 2},
                {"id": 9, "name": "访客", "roleType": 2},
            ],
        },
    }
    ok, msg, parsed = parse_auth_token_response(resp)
    assert ok is True
    assert msg == ""
    assert parsed is not None
    assert parsed.access_token == "abc123"
    assert [r.id for r in parsed.roles] == [3, 9]
