from src.sso.parsers.cas_parser import extract_login_error, parse_login_page


def test_parse_login_page_extracts_form_and_hidden_fields() -> None:
    html = """
    <html>
      <body>
        <form id="casLoginForm" action="/login?service=https://svc.example">
          <input type="hidden" name="execution" value="e1s1" />
          <input type="hidden" name="_eventId" value="submit" />
          <input type="text" name="username" />
          <input type="password" name="password" />
        </form>
      </body>
    </html>
    """
    parsed = parse_login_page(html, "https://sso.example/login?service=https://svc.example")
    assert parsed.form_action == "https://sso.example/login?service=https://svc.example"
    assert parsed.hidden_fields["execution"] == "e1s1"
    assert parsed.hidden_fields["_eventId"] == "submit"
    assert parsed.username_field == "username"
    assert parsed.password_field == "password"
    assert parsed.is_login_page is True


def test_parse_login_page_detects_captcha_and_error() -> None:
    html = """
    <html>
      <body>
        <form action="/login">
          <input type="hidden" name="execution" value="e1s2" />
          <input type="password" name="password" />
          <input type="text" name="captcha" />
          <img src="/captcha/image" />
        </form>
        <span class="error">用户名或密码错误</span>
      </body>
    </html>
    """
    parsed = parse_login_page(html, "https://sso.example/login")
    assert parsed.captcha_required is True
    assert parsed.captcha_challenge is not None
    assert parsed.captcha_challenge.image_url == "https://sso.example/captcha/image"
    assert parsed.captcha_challenge.field_name == "captcha"
    assert extract_login_error(html) == "用户名或密码错误"


def test_parse_login_page_ignores_hidden_captcha_label() -> None:
    html = """
    <html>
      <body>
        <form action="/login">
          <input type="hidden" name="execution" value="e1s3" />
          <input type="text" name="username" />
          <input type="password" name="password" />
          <span style="display: none;" id="captchaLabel">验证码</span>
        </form>
      </body>
    </html>
    """
    parsed = parse_login_page(html, "https://sso.example/login")
    assert parsed.captcha_required is False
    assert parsed.captcha_challenge is None


def test_parse_login_page_preserves_service_query_when_form_action_omits_it() -> None:
    html = """
    <html>
      <body>
        <form action="/login">
          <input type="hidden" name="execution" value="e1s4" />
          <input type="text" name="username" />
          <input type="password" name="password" />
        </form>
      </body>
    </html>
    """
    parsed = parse_login_page(
        html,
        "https://sso.example/login?service=https://pass.cc-pay.cn/login",
    )

    assert parsed.form_action == "https://sso.example/login?service=https://pass.cc-pay.cn/login"
