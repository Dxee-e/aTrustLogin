import os
import sys
import unittest
from unittest.mock import MagicMock, patch


sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import main as atrust_main


class FakeDriver:
    def __init__(self, destinations):
        self.destinations = iter(destinations)
        self.current_url = "data:,"
        self.cookies = {}
        self.added_cookies = []
        self.get_calls = []

    def get(self, url):
        self.get_calls.append(url)
        self.current_url = next(self.destinations)

    def get_cookie(self, name):
        return self.cookies.get(name)

    def delete_cookie(self, name):
        self.cookies.pop(name, None)

    def add_cookie(self, cookie):
        self.cookies[cookie["name"]] = cookie
        self.added_cookies.append(cookie)


def make_login(driver, cookie_tid=None, cookie_sig=None):
    login = atrust_main.ATrustLogin.__new__(atrust_main.ATrustLogin)
    login.driver = driver
    login.portal_address = "https://vpn.example.test/portal"
    login.portal_host = "vpn.example.test"
    login.cookie_tid = cookie_tid
    login.cookie_sig = cookie_sig
    login.delay_input = MagicMock()
    return login


class PortalCookieTests(unittest.TestCase):
    def test_open_portal_retries_until_portal_host_is_ready(self):
        driver = FakeDriver([
            "data:,",
            "chrome-error://chromewebdata/",
            "https://vpn.example.test/portal",
        ])
        login = make_login(driver)

        login.open_portal()

        self.assertEqual(3, len(driver.get_calls))
        self.assertEqual(["language", "lang"], [c["name"] for c in driver.added_cookies])
        self.assertTrue(all(c["domain"] == "vpn.example.test" for c in driver.added_cookies))

    def test_open_portal_never_sets_cookies_on_another_host(self):
        driver = FakeDriver(["https://error.example/"] * 3)
        login = make_login(driver)

        with self.assertRaisesRegex(RuntimeError, "configured host"):
            login.open_portal()

        self.assertEqual([], driver.added_cookies)

    def test_cli_cookies_require_portal_context(self):
        driver = FakeDriver([])
        driver.current_url = "https://error.example/"
        login = make_login(driver, cookie_tid="placeholder-tid", cookie_sig="placeholder-signature")

        with self.assertRaisesRegex(RuntimeError, "outside"):
            login.set_cli_cookie()

        self.assertEqual([], driver.added_cookies)


class MainRetryTests(unittest.TestCase):
    @patch.object(atrust_main, "ATrustLogin")
    def test_initialization_failure_is_retried_in_process(self, login_class):
        login = login_class.return_value
        login.init.side_effect = [RuntimeError("portal is starting"), None]
        login.is_logged.return_value = True

        atrust_main.main(
            portal_address="https://vpn.example.test/portal",
            username="placeholder-user",
            password="placeholder-password",
            keepalive=0,
            wait_atrust=False,
        )

        self.assertEqual(2, login.init.call_count)
        login.delay_loading.assert_called_once()
        login.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
