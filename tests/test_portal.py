import re
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlsplit

from semester import create_app

DEMO = [
    ("lera@demo.example", "Semestr-Lera-26"),
    ("misha@demo.example", "Semestr-Misha-26"),
]


def token(response, name="_csrf"):
    return re.search(fr'name="{name}" value="([^"]+)"', response.get_data(as_text=True))[1]


class PortalTest(unittest.TestCase):
    def setUp(self):
        self.sandbox = tempfile.TemporaryDirectory()
        self.addCleanup(self.sandbox.cleanup)
        self.config = {
            "TESTING": True,
            "SECRET_KEY": "test-key",
            "DATABASE": str(Path(self.sandbox.name) / "db.sqlite3"),
            "SESSION_COOKIE_SECURE": False,
        }
        self.app = create_app(self.config)
        self.browser = self.app.test_client()

    def login(self, browser=None, account=0, password=None):
        browser = browser or self.browser
        email, expected = DEMO[account]
        return browser.post("/login", data={
            "_csrf": token(browser.get("/login")), "email": email,
            "password": expected if password is None else password,
        })

    def send_request(self, browser=None):
        browser = browser or self.browser
        form = browser.get("/requests/new/study")
        return browser.post("/requests/new/study", data={
            "_csrf": token(form), "nonce": token(form, "nonce"),
            "delivery": "digital", "comment": "Для подачи документов",
        })

    def test_private_page_requires_login_and_logout_revokes_session(self):
        self.assertEqual(urlsplit(self.browser.get("/profile").location).path, "/login")
        self.assertEqual(self.login().status_code, 303)
        profile = self.browser.get("/profile")
        self.assertIn("Валерия Маякова", profile.get_data(as_text=True))
        previous_cookie = self.browser.get_cookie("session").value
        self.browser.post("/logout", data={"_csrf": token(profile)})
        replay = self.app.test_client()
        replay.set_cookie("session", previous_cookie)
        self.assertEqual(urlsplit(replay.get("/profile").location).path, "/login")

    def test_wrong_password_does_not_log_in(self):
        self.assertEqual(self.login(password="invalid").status_code, 401)
        self.assertEqual(self.browser.get("/").status_code, 303)

    def test_login_requires_csrf(self):
        email, password = DEMO[0]
        response = self.browser.post("/login", data={"email": email, "password": password})
        self.assertEqual(response.status_code, 400)

    def test_request_owner_and_document_are_private(self):
        self.login()
        result = self.send_request()
        self.assertEqual(result.status_code, 303)
        path = urlsplit(result.location).path
        self.assertIn("Для подачи документов", self.browser.get(path).get_data(as_text=True))
        other = self.app.test_client()
        self.login(other, 1)
        self.assertEqual(other.get(path).status_code, 404)
        self.assertEqual(other.get(path + "/document").status_code, 404)
        self.assertNotIn("Для подачи документов", other.get("/requests").get_data(as_text=True))
        self.assertIn("Михаил Ратников", other.get("/profile").get_data(as_text=True))

    def test_request_is_idempotent_and_survives_app_restart(self):
        self.login()
        form = self.browser.get("/requests/new/study")
        params = {"_csrf": token(form), "nonce": token(form, "nonce"), "delivery": "digital"}
        first = self.browser.post("/requests/new/study", data=params)
        retry = self.browser.post("/requests/new/study", data=params)
        self.assertEqual(first.location, retry.location)
        restarted = create_app(self.config).test_client()
        self.login(restarted)
        self.assertEqual(restarted.get(first.location).status_code, 200)

    def test_schedule_and_grades_differ_between_students(self):
        self.login()
        other = self.app.test_client()
        self.login(other, 1)
        first = self.browser.get("/schedule?view=week").get_data(as_text=True)
        second = other.get("/schedule?view=week").get_data(as_text=True)
        self.assertIn("Маркетинговая аналитика", first)
        self.assertNotIn("Маркетинговая аналитика", second)
        self.assertIn("Международная экономика", second)
        self.assertIn("Методы исследований", self.browser.get("/grades").get_data(as_text=True))
        self.assertNotIn("Методы исследований", other.get("/grades").get_data(as_text=True))

    def test_notification_read_action_belongs_to_signed_in_account(self):
        self.login()
        other = self.app.test_client()
        self.login(other, 1)
        self.assertEqual(other.get("/notifications/schedule-a").status_code, 404)
        page = self.browser.get("/notifications")
        result = self.browser.post("/notifications/read", data={
            "_csrf": token(page), "notice_id": "schedule-a",
        })
        self.assertEqual(result.status_code, 303)
        self.assertNotIn('data-unread="schedule-a"', self.browser.get("/notifications").get_data(as_text=True))

    def test_invalid_request_payload_stays_on_form(self):
        self.login()
        form = self.browser.get("/requests/new/study")
        result = self.browser.post("/requests/new/study", data={
            "_csrf": token(form), "nonce": token(form, "nonce"),
            "delivery": "unknown", "comment": "<script>alert(1)</script>",
        })
        self.assertEqual(result.status_code, 422)
        self.assertNotIn("<script>alert(1)</script>", result.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
