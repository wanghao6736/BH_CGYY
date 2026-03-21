from argparse import Namespace

from src.config.settings import ApiSettings, UserSettings
from src.main import merge_cli_overrides


def test_merge_cli_overrides_ignores_missing_business_args_for_profile_command() -> None:
    api_settings = ApiSettings()
    user_settings = UserSettings()

    merge_cli_overrides(
        Namespace(cmd="profile", profile_cmd="list"),
        api_settings,
        user_settings,
    )

    assert api_settings.venue_site_id == ApiSettings.venue_site_id
    assert user_settings.profile_name == UserSettings.profile_name
