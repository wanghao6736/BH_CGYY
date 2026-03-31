from src.cli.parser import build_parser


def test_parser_accepts_profile_on_business_command() -> None:
    parser = build_parser()

    args = parser.parse_args(["reserve", "-P", "alice", "-d", "2026/2/3"])

    assert args.cmd == "reserve"
    assert args.profile == "alice"
    assert args.date == "2026/2/3"


def test_parser_accepts_profile_subcommand_set_and_unset() -> None:
    parser = build_parser()

    args = parser.parse_args(
        ["profile", "modify", "alice", "-s", "CGYY_PHONE=13800138000", "-u", "CGYY_BUDDY_IDS"]
    )

    assert args.cmd == "profile"
    assert args.profile_cmd == "modify"
    assert args.name == "alice"
    assert args.set_values == ["CGYY_PHONE=13800138000"]
    assert args.unset_keys == ["CGYY_BUDDY_IDS"]


def test_parser_accepts_profile_cleanup_legacy_sso() -> None:
    parser = build_parser()

    args = parser.parse_args(["profile", "cleanup-legacy-sso", "alice"])

    assert args.cmd == "profile"
    assert args.profile_cmd == "cleanup-legacy-sso"
    assert args.name == "alice"


def test_parser_accepts_config_doctor_probe() -> None:
    parser = build_parser()

    args = parser.parse_args(["config-doctor", "-P", "alice", "--probe"])

    assert args.cmd == "config-doctor"
    assert args.profile == "alice"
    assert args.probe is True


def test_parser_accepts_pay_options() -> None:
    parser = build_parser()

    args = parser.parse_args(
        [
            "pay",
            "-P",
            "alice",
            "-t",
            "D260331000575",
            "--mode",
            "mobile",
            "--pay-way-name",
            "wxpay_wap",
        ]
    )

    assert args.cmd == "pay"
    assert args.profile == "alice"
    assert args.trade_no == "D260331000575"
    assert args.mode == "mobile"
    assert args.pay_way_name == "wxpay_wap"
