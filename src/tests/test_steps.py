from __future__ import annotations

"""
分步手动测试脚本：

运行方式（在项目根目录）：
  1) 只测验证码拉取与图片保存：
     python -m src.tests.test_steps --step fetch_captcha

  2) 测试验证码完整校验（包含 OCR 点击点计算与 /captcha/check）：
     python -m src.tests.test_steps --step verify_captcha

  3) 测试当日场地信息查询：
     python -m src.tests.test_steps --step info

  4) 测试完整预约流程（验证码 + 下单）：
     python -m src.tests.test_steps --step full
"""

import argparse
import random
import time

from src.config.settings import load_settings
from src.main import build_app


def step_fetch_captcha() -> None:
    workflow, _ = build_app()
    captcha_data = workflow.captcha_service.fetch_captcha()
    print("secret_key:", captcha_data.secret_key)
    print("token:", captcha_data.token)
    print("word_list:", captcha_data.word_list)
    print("image_path:", captcha_data.image_path)


def step_verify_captcha() -> None:
    api_settings, _, _, _ = load_settings()
    workflow, _ = build_app()
    captcha_data = workflow.captcha_service.fetch_captcha()
    time.sleep(random.uniform(api_settings.captcha_delay_min, api_settings.captcha_delay_max))
    result = workflow.captcha_service.verify_captcha(captcha_data)
    print("captcha verify success:", result.success)
    print("captcha message:", result.message)
    print("point_json:", result.verification.point_json)
    print("verify_json:", result.verification.verify_json)


def step_info() -> None:
    workflow, _ = build_app()
    success, message, slots = workflow.reservation_service.get_info_parsed()
    print("day info success:", success)
    print("day info message:", message)
    print("day info slots:", slots)


def step_order_detail() -> None:
    workflow, _ = build_app()
    success, message, order_detail = workflow.reservation_service.get_order_detail_parsed("D260306000729")
    print("order detail success:", success)
    print("order detail message:", message)
    print("order detail order_detail:", order_detail)


def step_full() -> None:
    workflow, _ = build_app()
    success, message, submit = workflow.reservation_service.submit_reservation()
    print("submit success:", success)
    print("submit message:", message)
    print("submit submit:", submit)


def main() -> None:
    parser = argparse.ArgumentParser(description="分步测试 CGYY 预约流程")
    parser.add_argument(
        "--step",
        choices=["fetch_captcha", "verify_captcha", "info", "order_detail", "full"],
        default="full",
        help="要执行的测试步骤",
    )
    args = parser.parse_args()

    if args.step == "fetch_captcha":
        step_fetch_captcha()
    elif args.step == "verify_captcha":
        step_verify_captcha()
    elif args.step == "info":
        step_info()
    elif args.step == "order_detail":
        step_order_detail()
    elif args.step == "full":
        step_full()


if __name__ == "__main__":
    main()
