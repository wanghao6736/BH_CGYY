"""CGYY 业务异常层级。"""


class CgyyError(Exception):
    """所有业务异常的基类。"""


class QueryError(CgyyError):
    """场地查询 / 方案搜索失败。"""


class CaptchaError(CgyyError):
    """验证码获取或校验失败。"""


class BuddyConfigError(CgyyError):
    """同伴配置不满足场地要求。"""
