from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Tuple
from urllib.parse import urljoin

from src.sso.adapters.base import ServiceAdapter
from src.sso.api.page_client import PageClient
from src.sso.exceptions import (SsoCaptchaRequired, SsoLoginFailed,
                                SsoRedirectLoopError, SsoServiceNotReady)
from src.sso.models import (Credentials, PageResponse, RedirectStep,
                            SsoLoginResult)
from src.sso.providers.cas_provider import CasProvider

logger = logging.getLogger(__name__)


@dataclass
class SsoLoginService:
    provider: CasProvider
    page_client: PageClient
    max_redirects: int = 10

    def _follow_redirects(self, initial_resp: PageResponse) -> Tuple[PageResponse, list[RedirectStep]]:
        current_resp = initial_resp
        chain: list[RedirectStep] = []
        for _ in range(max(self.max_redirects, 1) + 1):
            chain.append(
                RedirectStep(
                    request_url=current_resp.url,
                    status_code=current_resp.status_code,
                    location=current_resp.location,
                )
            )
            if 300 <= current_resp.status_code < 400 and current_resp.location:
                next_url = urljoin(current_resp.url, current_resp.location)
                logger.info("跟随重定向 %s -> %s", current_resp.url, next_url)
                current_resp = self.page_client.get_page(next_url)
                continue
            return current_resp, chain
        raise SsoRedirectLoopError(f"重定向次数超过上限: {self.max_redirects}")

    def login(self, adapter: ServiceAdapter, credentials: Credentials) -> SsoLoginResult:
        entry_url = self.provider.build_login_entry_url(adapter.service_url)
        logger.info("访问统一认证入口 service=%s url=%s", adapter.service_name, entry_url)
        entry_resp = self.page_client.get_page(entry_url)
        if 300 <= entry_resp.status_code < 400 and entry_resp.location:
            final_resp, chain = self._follow_redirects(entry_resp)
            if adapter.is_service_response(final_resp):
                state = adapter.collect_auth_state(self.page_client)
                return SsoLoginResult(
                    success=True,
                    message="已复用现有 SSO 登录态",
                    final_url=final_resp.url,
                    redirect_chain=chain,
                    cookies={"cookie": state.cookie},
                )

        context = self.provider.parse_login_page(entry_resp)
        if not context.form_action:
            raise SsoLoginFailed("未找到统一认证登录表单")
        if context.captcha_required and not credentials.captcha:
            raise SsoCaptchaRequired("统一认证页面要求验证码，当前未提供验证码能力")

        form = self.provider.build_login_form(context, credentials)
        logger.info("提交统一认证表单 action=%s", context.form_action)
        submit_resp = self.page_client.post_form(context.form_action, form)
        submit_chain = [
            RedirectStep(
                request_url=context.form_action,
                status_code=submit_resp.status_code,
                location=submit_resp.location,
            )
        ]

        if submit_resp.status_code == 200:
            submit_context = self.provider.parse_login_page(submit_resp)
            if submit_context.error_message:
                raise SsoLoginFailed(submit_context.error_message)
            if submit_context.is_continue_page:
                cont_form = self.provider.build_continue_form(submit_context)
                logger.info("检测到中间确认页，继续提交 action=%s", submit_context.form_action)
                submit_resp = self.page_client.post_form(submit_context.form_action, cont_form)
                submit_chain.append(
                    RedirectStep(
                        request_url=submit_context.form_action,
                        status_code=submit_resp.status_code,
                        location=submit_resp.location,
                    )
                )

        if 300 <= submit_resp.status_code < 400 and submit_resp.location:
            final_resp, chain = self._follow_redirects(submit_resp)
            submit_chain.extend(chain)
        else:
            final_resp = submit_resp
        final_resp = adapter.initialize_service_session(self.page_client, final_resp)
        if not adapter.is_service_response(final_resp):
            raise SsoServiceNotReady(f"未成功进入目标服务页面: {final_resp.url}")
        state = adapter.collect_auth_state(self.page_client)
        return SsoLoginResult(
            success=True,
            message="统一认证登录成功",
            final_url=final_resp.url,
            redirect_chain=submit_chain,
            cookies={"cookie": state.cookie},
        )
