import re
import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

from semester import create_app
from semester.demo import academic_results

DEMO = [
    ("lera@demo.example", "Semestr-Lera-26"),
    ("misha@demo.example", "Semestr-Misha-26"),
    ("dean@demo.example", "Semestr-Dean-26"),
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
            "_csrf": token(browser.get("/login")),
            "email": email,
            "password": expected if password is None else password,
        })

    def send_request(self, browser=None):
        browser = browser or self.browser
        form = browser.get("/requests/new/study")
        return browser.post("/requests/new/study", data={
            "_csrf": token(form),
            "nonce": token(form, "nonce"),
            "delivery": "digital",
            "comment": "Для подачи документов",
        })

    def test_private_page_requires_login_and_logout_revokes_session(self):
        self.assertEqual(urlsplit(self.browser.get("/profile").location).path, "/login")
        self.assertEqual(self.login().status_code, 303)
        profile = self.browser.get("/profile")
        self.assertIn("Валерия Маякова", profile.get_data(as_text=True))
        self.assertIn("24-МП-0184", profile.get_data(as_text=True))
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

    def test_schedule_ics_export_requires_auth_and_matches_student(self):
        self.assertEqual(urlsplit(self.browser.get("/schedule.ics").location).path, "/login")
        self.login()
        ics = self.browser.get("/schedule.ics")
        self.assertEqual(ics.status_code, 200)
        self.assertIn("text/calendar", ics.headers["Content-Type"])
        body = ics.get_data(as_text=True)
        self.assertIn("BEGIN:VCALENDAR", body)
        self.assertIn("Маркетинговая аналитика", body)
        self.assertNotIn("Международная экономика", body)

    def test_notification_read_action_belongs_to_signed_in_account(self):
        self.login()
        other = self.app.test_client()
        self.login(other, 1)
        self.assertEqual(other.get("/notifications/schedule-a").status_code, 404)
        page = self.browser.get("/notifications")
        result = self.browser.post("/notifications/read", data={
            "_csrf": token(page),
            "notice_id": "schedule-a",
        })
        self.assertEqual(result.status_code, 303)
        self.assertNotIn('data-unread="schedule-a"', self.browser.get("/notifications").get_data(as_text=True))

    def test_exam_calendar_stays_stable_through_judging(self):
        before = academic_results(1, date(2026, 11, 22))
        after = academic_results(1, date(2026, 11, 28))
        self.assertEqual(before, after)

    def test_document_ready_notification_opens_owned_document(self):
        self.login()
        response = self.send_request()
        path = urlsplit(response.location).path
        self.assertEqual(self.browser.get(path + "/document").status_code, 404)
        with closing(sqlite3.connect(self.config["DATABASE"])) as database, database:
            database.execute("UPDATE requests SET ready_at = 0 WHERE id = ?", (path.split("/")[-1],))
        notices = self.browser.get("/notifications").get_data(as_text=True)
        self.assertIn("Справка об обучении готова", notices)
        notice_id = "request-" + path.split("/")[-1]
        self.assertIn(f'data-unread="{notice_id}"', notices)
        detail = self.browser.get("/notifications/" + notice_id).get_data(as_text=True)
        self.assertIn(path + "/document", detail)
        self.assertIn("Валерия Ильинична", self.browser.get(path + "/document").get_data(as_text=True))
        other = self.app.test_client()
        self.login(other, 1)
        self.assertEqual(other.get("/notifications/" + notice_id).status_code, 404)

    def test_invalid_request_payload_stays_on_form(self):
        self.login()
        form = self.browser.get("/requests/new/study")
        result = self.browser.post("/requests/new/study", data={
            "_csrf": token(form),
            "nonce": token(form, "nonce"),
            "delivery": "unknown",
            "comment": "<script>alert(1)</script>",
        })
        self.assertEqual(result.status_code, 422)
        self.assertNotIn("<script>alert(1)</script>", result.get_data(as_text=True))

    def test_staff_queue_resolution_and_group_announcements_are_role_isolated(self):
        # Student cannot access /staff
        self.login()
        self.assertEqual(self.browser.get("/staff").status_code, 404)
        appeal_form = self.browser.get("/requests/new/appeal")
        created = self.browser.post("/requests/new/appeal", data={
            "_csrf": token(appeal_form),
            "nonce": token(appeal_form, "nonce"),
            "comment": "Прошу перенести сдачу зачёта по уважительной причине.",
        })
        req_path = urlsplit(created.location).path
        req_id = req_path.split("/")[-1]

        # Staff logs in and is redirected to /staff
        staff = self.app.test_client()
        login_res = self.login(staff, 2)
        self.assertEqual(urlsplit(login_res.location).path, "/staff")
        self.assertEqual(urlsplit(staff.get("/").location).path, "/staff")
        staff_page = staff.get("/staff")
        self.assertEqual(staff_page.status_code, 200)
        self.assertIn(req_id[:8].upper(), staff_page.get_data(as_text=True))

        # Staff resolves the student's appeal with an official reply
        resolved = staff.post(f"/staff/requests/{req_id}/resolve", data={
            "_csrf": token(staff_page),
            "staff_note": "Заявление согласовано, перенос назначен на резервный день.",
        })
        self.assertEqual(resolved.status_code, 303)
        self.assertIn(
            "Заявление согласовано, перенос назначен на резервный день.",
            self.browser.get(req_path).get_data(as_text=True),
        )
        self.assertIn(
            "Ответ деканата по заявлению",
            self.browser.get("/notifications").get_data(as_text=True),
        )

        # Staff publishes an announcement strictly for МП-24-1
        staff_page = staff.get("/staff")
        announced = staff.post("/staff/announcements", data={
            "_csrf": token(staff_page),
            "target_group": "МП-24-1",
            "kind": "Расписание",
            "title": "Дополнительная консультация в Б–302",
            "body": "В четверг в 16:00 пройдёт разбор проектных работ группы МП-24-1.",
        })
        self.assertEqual(announced.status_code, 303)
        self.assertIn(
            "Дополнительная консультация в Б–302",
            self.browser.get("/notifications").get_data(as_text=True),
        )
        other_student = self.app.test_client()
        self.login(other_student, 1)
        self.assertNotIn(
            "Дополнительная консультация в Б–302",
            other_student.get("/notifications").get_data(as_text=True),
        )

    def test_pages_contain_no_inline_styles_or_scripts_for_strict_csp(self):
        login_html = self.browser.get("/login").get_data(as_text=True)
        self.assertNotRegex(login_html, r"\sstyle=")
        self.assertNotRegex(login_html, r"<script(?![^>]*\bsrc=)")
        self.login()
        for path in ("/", "/schedule", "/schedule?view=week", "/grades", "/requests",
                     "/requests/new/study", "/notifications", "/profile"):
            html = self.browser.get(path).get_data(as_text=True)
            self.assertNotRegex(html, r"\sstyle=", msg=path)
            self.assertNotRegex(html, r"<script(?![^>]*\bsrc=)", msg=path)
        staff = self.app.test_client()
        self.login(staff, 2)
        for path in ("/staff", "/profile"):
            html = staff.get(path).get_data(as_text=True)
            self.assertNotRegex(html, r"\sstyle=", msg=path)
            self.assertNotRegex(html, r"<script(?![^>]*\bsrc=)", msg=path)


if __name__ == "__main__":
    unittest.main()
