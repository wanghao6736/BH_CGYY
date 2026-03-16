"""SSO 登录异常。"""


class SsoError(Exception):
    """SSO 异常基类。"""


class SsoPageParseError(SsoError):
    """登录页解析失败。"""


class SsoLoginFailed(SsoError):
    """用户名密码错误或认证中心拒绝。"""


class SsoCaptchaRequired(SsoError):
    """认证中心要求验证码，但当前未提供。"""


class SsoRedirectLoopError(SsoError):
    """重定向链异常或超出上限。"""


class SsoServiceNotReady(SsoError):
    """已退出认证中心，但目标服务未建立登录态。"""
