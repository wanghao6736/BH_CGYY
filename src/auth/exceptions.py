"""认证与会话管理异常。"""


class AuthError(Exception):
    """认证层异常基类。"""


class AuthProbeError(AuthError):
    """服务登录态探测失败。"""


class AuthUnavailableError(AuthError):
    """缺少可用的认证信息。"""
