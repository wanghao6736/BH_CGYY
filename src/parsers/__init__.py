# Parsers: pure functions on dict/JSON, no request coupling.
# Test with: data = json.load(open("docs/get_info.json"))["data"]

from src.parsers.captcha import (CaptchaParsed, CheckCaptchaParsed,
                                 parse_captcha_data, parse_captcha_response,
                                 parse_check_captcha_data,
                                 parse_check_captcha_response)
from src.parsers.catalog import (CatalogParsed, SiteItem, SportItem,
                                 parse_catalog_data, parse_catalog_response)
from src.parsers.common import get_by_path, parse_success_message
from src.parsers.day_info import (DayInfoParsed, parse_info_data,
                                  parse_info_response)
from src.parsers.order import (OrderDetailParsed, OrderSpaceItem, SubmitParsed,
                               parse_order_detail_data,
                               parse_order_detail_response, parse_submit_data,
                               parse_submit_response)
from src.parsers.slot_filter import (SlotChoice, SlotSolution,
                                     find_available_slots)

__all__ = [
    "CaptchaParsed",
    "CheckCaptchaParsed",
    "parse_captcha_data",
    "parse_captcha_response",
    "parse_check_captcha_data",
    "parse_check_captcha_response",
    "CatalogParsed",
    "SportItem",
    "SiteItem",
    "parse_catalog_data",
    "parse_catalog_response",
    "get_by_path",
    "parse_success_message",
    "DayInfoParsed",
    "parse_info_data",
    "parse_info_response",
    "find_available_slots",
    "SlotChoice",
    "SlotSolution",
    "SubmitParsed",
    "parse_submit_data",
    "parse_submit_response",
    "OrderDetailParsed",
    "OrderSpaceItem",
    "parse_order_detail_data",
    "parse_order_detail_response",
]
