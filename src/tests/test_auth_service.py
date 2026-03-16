from src.auth.cgyy_auth_service import CgyyAuthService


class _FakeAuthApi:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    def login_with_sso_token(self, sso_token: str):
        self.calls.append(("login", sso_token))
        return {
            "code": 200,
            "data": {
                "token": {"access_token": "init-token"},
                "roles": [
                    {"id": 9, "name": "访客", "roleType": 2},
                    {"id": 3, "name": "学生", "roleType": 2},
                ],
            },
        }

    def role_login(self, role_id: int, cg_authorization: str):
        self.calls.append(("role_login", (role_id, cg_authorization)))
        return {
            "code": 200,
            "data": {
                "token": {"access_token": "final-token"},
                "roles": [{"id": role_id, "name": "学生", "roleType": 2}],
            },
        }


def test_exchange_cg_authorization_prefers_default_role() -> None:
    api = _FakeAuthApi()
    service = CgyyAuthService(api)  # type: ignore[arg-type]
    result = service.exchange_cg_authorization("sso-token")
    assert result.cg_authorization == "final-token"
    assert result.role_id == 3
    assert api.calls == [
        ("login", "sso-token"),
        ("role_login", (3, "init-token")),
    ]


def test_exchange_cg_authorization_falls_back_to_first_role() -> None:
    class _FallbackAuthApi(_FakeAuthApi):
        def login_with_sso_token(self, sso_token: str):
            self.calls.append(("login", sso_token))
            return {
                "code": 200,
                "data": {
                    "token": {"access_token": "init-token"},
                    "roles": [{"id": 7, "name": "教师", "roleType": 2}],
                },
            }

    api = _FallbackAuthApi()
    service = CgyyAuthService(api)  # type: ignore[arg-type]
    result = service.exchange_cg_authorization("sso-token")
    assert result.role_id == 7
    assert api.calls[-1] == ("role_login", (7, "init-token"))
