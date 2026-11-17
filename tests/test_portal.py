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


def decode_rendered_qr(html, index=0):
    """Rasterize the <svg class="qr-svg"> emitted in HTML and decode with OpenCV QRCodeDetector."""
    matches = list(re.finditer(
        r'<svg class="qr-svg"[^>]*viewBox="0 0 (\d+) \1"[^>]*>.*?<path d="([^"]+)"',
        html,
        re.DOTALL,
    ))
    assert matches, "No .qr-svg found in HTML"
    dim_str, path_d = matches[index].groups()
    dim = int(dim_str)
    scale = 10
    import cv2
    import numpy as np
    canvas = np.full((dim * scale, dim * scale, 3), 255, dtype=np.uint8)
    for x_s, y_s, w_s in re.findall(r"M(\d+) (\d+)h(\d+)v1h-\d+z", path_d):
        x, y, w = int(x_s), int(y_s), int(w_s)
        canvas[y * scale:(y + 1) * scale, x * scale:(x + w) * scale] = 0
    decoded, _, _ = cv2.QRCodeDetector().detectAndDecode(canvas)
    return decoded


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

    def test_instant_certificates_issue_immediately_with_specialized_sheets(self):
        self.login()
        reqs_page = self.browser.get("/requests")
        res = self.browser.post("/requests/instant/military", data={
            "_csrf": token(reqs_page),
            "nonce": token(reqs_page, "nonce"),
        })
        self.assertEqual(res.status_code, 303)
        doc_path = urlsplit(res.location).path
        self.assertTrue(doc_path.endswith("/document"))
        doc_html = self.browser.get(doc_path).get_data(as_text=True)
        self.assertIn("Приложение № 4", doc_html)
        self.assertIn("38.03.02 Менеджмент", doc_html)

        # Income statement contains 6-month payout table
        reqs_page2 = self.browser.get("/requests")
        inc_res = self.browser.post("/requests/instant/income", data={
            "_csrf": token(reqs_page2),
            "nonce": token(reqs_page2, "nonce"),
        })
        inc_html = self.browser.get(urlsplit(inc_res.location).path).get_data(as_text=True)
        self.assertIn("ГАС + рейтинговая надбавка", inc_html)

        # Other student gets 404 on instant document
        other = self.app.test_client()
        self.login(other, 1)
        self.assertEqual(other.get(doc_path).status_code, 404)

    def test_dormitory_payment_is_idempotent_and_receipt_is_owner_isolated(self):
        self.login()
        campus_page = self.browser.get("/campus")
        self.assertEqual(campus_page.status_code, 200)
        self.assertIn("ОД-24/412", campus_page.get_data(as_text=True))
        # Unpaid receipt is 404 before payment
        self.assertEqual(self.browser.get("/campus/receipt/chg-1-nov").status_code, 404)

        # Other student cannot pay Lera's dorm charge
        other = self.app.test_client()
        self.login(other, 1)
        other_campus = other.get("/campus")
        self.assertEqual(
            other.post("/campus/pay/chg-1-nov", data={"_csrf": token(other_campus), "method": "sbp"}).status_code,
            404,
        )

        # Lera pays her November dorm charge (idempotent on retry)
        pay1 = self.browser.post("/campus/pay/chg-1-nov", data={"_csrf": token(campus_page), "method": "sbp"})
        self.assertEqual(pay1.status_code, 303)
        pay2 = self.browser.post("/campus/pay/chg-1-nov", data={"_csrf": token(campus_page), "method": "sbp"})
        self.assertEqual(pay1.location, pay2.location)

        receipt = self.browser.get("/campus/receipt/chg-1-nov")
        self.assertEqual(receipt.status_code, 200)
        self.assertIn("Подтверждение платежа", receipt.get_data(as_text=True))
        self.assertIn("3 400 ₽", receipt.get_data(as_text=True))
        # Other student cannot read Lera's receipt
        self.assertEqual(other.get("/campus/receipt/chg-1-nov").status_code, 404)

    def test_guest_pass_and_coworking_booking_enforce_ownership(self):
        self.login()
        campus_page = self.browser.get("/campus")
        csrf_tok = token(campus_page)
        visit_date = re.search(r'<select id="guest_date" name="visit_date">\s*<option value="([^"]+)"', campus_page.get_data(as_text=True))[1]

        gp = self.browser.post("/campus/guest-pass", data={
            "_csrf": csrf_tok,
            "guest_name": "Маяков Илья Сергеевич",
            "visit_date": visit_date,
            "location": "Студдом № 2",
        })
        self.assertEqual(gp.status_code, 303)
        updated_html = self.browser.get("/campus").get_data(as_text=True)
        self.assertIn("Маяков Илья Сергеевич", updated_html)
        pass_id = re.search(r'/campus/guest-pass/([0-9a-f]+)/revoke', updated_html)[1]

        bk = self.browser.post("/campus/book-room", data={
            "_csrf": csrf_tok,
            "space_id": "box-k1",
            "booking_date": visit_date,
            "slot_label": "11:35–13:00",
            "purpose": "Подготовка кейса",
        })
        self.assertEqual(bk.status_code, 303)
        updated_html = self.browser.get("/campus").get_data(as_text=True)
        self.assertIn("Проектный бокс К–1", updated_html)
        booking_id = re.search(r'/campus/book-room/([0-9a-f]+)/cancel', updated_html)[1]

        # Other student cannot revoke Lera's guest pass or room booking
        other = self.app.test_client()
        self.login(other, 1)
        other_csrf = token(other.get("/campus"))
        self.assertEqual(other.post(f"/campus/guest-pass/{pass_id}/revoke", data={"_csrf": other_csrf}).status_code, 404)
        self.assertEqual(other.post(f"/campus/book-room/{booking_id}/cancel", data={"_csrf": other_csrf}).status_code, 404)

    def test_smart_navigator_personalizes_context_per_student(self):
        self.login()
        lera_nav = self.browser.get("/navigator?q=общежитие").get_data(as_text=True)
        self.assertIn("ОД-24/412", lera_nav)
        self.assertNotIn("ОД-23/109", lera_nav)

        other = self.app.test_client()
        self.login(other, 1)
        misha_nav = other.get("/navigator?q=общежитие").get_data(as_text=True)
        self.assertIn("ОД-23/109", misha_nav)
        self.assertNotIn("ОД-24/412", misha_nav)

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

    def test_staff_queue_return_schedule_override_and_announcements(self):
        # Student cannot access any /staff route
        self.login()
        for st_path in ("/staff", "/staff/schedule", "/staff/students", "/staff/notices"):
            self.assertEqual(self.browser.get(st_path).status_code, 404)

        med_form = self.browser.get("/requests/new/medical")
        created = self.browser.post("/requests/new/medical", data={
            "_csrf": token(med_form),
            "nonce": token(med_form, "nonce"),
            "subject": "Форма 095/у",
            "comment": "Болела с 10 по 14 ноября, справка поликлиники № 209.",
        })
        req_path = urlsplit(created.location).path
        req_id = req_path.split("/")[-1]

        # Staff logs in
        staff = self.app.test_client()
        login_res = self.login(staff, 2)
        self.assertEqual(urlsplit(login_res.location).path, "/staff")

        # Return petition for revision
        staff_page = staff.get("/staff")
        returned = staff.post(f"/staff/requests/{req_id}/resolve", data={
            "_csrf": token(staff_page),
            "decision": "returned",
            "staff_note": "Приложите номер бланка справки 095/у.",
        })
        self.assertEqual(returned.status_code, 303)
        detail_html = self.browser.get(req_path).get_data(as_text=True)
        self.assertIn("Возвращено", detail_html)
        self.assertIn("Приложите номер бланка справки 095/у.", detail_html)
        self.assertEqual(self.browser.get(req_path + "/document").status_code, 404)

        # Staff sets live room override for МП-24-1 Monday 10:00 -> Б–302
        sched_page = staff.get("/staff/schedule?group=МП-24-1")
        ov_res = staff.post("/staff/schedule/override", data={
            "_csrf": token(sched_page),
            "student_group": "МП-24-1",
            "weekday": "0",
            "start_time": "10:00",
            "new_room": "Б–302",
            "note": "Замена проектора",
        })
        self.assertEqual(ov_res.status_code, 303)
        self.assertIn("Б–302", self.browser.get("/schedule?view=week").get_data(as_text=True))
        self.assertIn("Перенос из А–302", self.browser.get("/schedule.ics").get_data(as_text=True))

        # Staff publishes announcement strictly for МП-24-1
        notices_page = staff.get("/staff/notices")
        announced = staff.post("/staff/announcements", data={
            "_csrf": token(notices_page),
            "target_group": "МП-24-1",
            "kind": "Деканат",
            "title": "Приём документов на ПГАС до пятницы",
            "body": "Загрузите перечень публикаций и кейсов до 18:00 пятницы.",
        })
        self.assertEqual(announced.status_code, 303)
        self.assertIn("Приём документов на ПГАС до пятницы", self.browser.get("/notifications").get_data(as_text=True))

        other_student = self.app.test_client()
        self.login(other_student, 1)
        self.assertNotIn("Приём документов на ПГАС до пятницы", other_student.get("/notifications").get_data(as_text=True))

    def test_pages_contain_no_inline_styles_or_scripts_for_strict_csp(self):
        login_html = self.browser.get("/login").get_data(as_text=True)
        self.assertNotRegex(login_html, r"\sstyle=")
        self.assertNotRegex(login_html, r"<script(?![^>]*\bsrc=)")
        self.login()
        for path in (
            "/", "/navigator", "/schedule", "/schedule?view=week", "/grades",
            "/requests", "/requests/new/study", "/requests/new/medical",
            "/campus", "/campus/receipt/chg-1-oct", "/notifications", "/profile",
        ):
            html = self.browser.get(path).get_data(as_text=True)
            self.assertNotRegex(html, r"\sstyle=", msg=path)
            self.assertNotRegex(html, r"<script(?![^>]*\bsrc=)", msg=path)
        staff = self.app.test_client()
        self.login(staff, 2)
        for path in ("/staff", "/staff/schedule", "/staff/students", "/staff/notices", "/profile"):
            html = staff.get(path).get_data(as_text=True)
            self.assertNotRegex(html, r"\sstyle=", msg=path)
            self.assertNotRegex(html, r"<script(?![^>]*\bsrc=)", msg=path)

    def test_login_rate_limit_blocks_after_five_failures(self):
        for _ in range(5):
            res = self.login(password="wrong-password")
            self.assertEqual(res.status_code, 401)
        blocked = self.login()  # 6th attempt even with valid password must be 429
        self.assertEqual(blocked.status_code, 429)
        self.assertIn("Слишком много неудачных попыток входа", blocked.get_data(as_text=True))

    def test_public_qr_verify_masks_name_and_enforces_revoke_ownership(self):
        self.login()
        reqs_page = self.browser.get("/requests")
        issued = self.browser.post("/requests/instant/military", data={
            "_csrf": token(reqs_page),
            "nonce": token(reqs_page, "nonce"),
        })
        doc_path = urlsplit(issued.location).path
        req_id = doc_path.split("/")[-2]
        doc_html = self.browser.get(doc_path).get_data(as_text=True)
        self.assertIn("ОБРАЗЕЦ / ДЕМО", doc_html)
        verify_path = re.search(r'href="(/verify/[A-Za-z0-9_-]+)"', doc_html)[1]

        # Anonymous public verification shows masked name, not full name or email
        anon = self.app.test_client()
        pub_res = anon.get(verify_path)
        self.assertEqual(pub_res.status_code, 200)
        pub_html = pub_res.get_data(as_text=True)
        self.assertIn("Подлинность подтверждена", pub_html)
        self.assertIn("Маякова В. И.", pub_html)
        self.assertNotIn("Валерия Ильинична Маякова", pub_html)
        self.assertNotIn("lera@demo.example", pub_html)
        self.assertNotRegex(pub_html, r"\sstyle=")

        # Other student cannot revoke Lera's certificate (IDOR -> 404)
        other = self.app.test_client()
        self.login(other, 1)
        other_csrf = token(other.get("/requests"))
        self.assertEqual(other.post(f"/requests/{req_id}/revoke", data={"_csrf": other_csrf}).status_code, 404)

        # Owner revokes certificate -> public page immediately reflects revocation
        owner_verify = self.browser.get(verify_path)
        rev = self.browser.post(f"/requests/{req_id}/revoke", data={"_csrf": token(owner_verify)})
        self.assertEqual(rev.status_code, 303)
        self.assertIn("Документ отозван", anon.get(verify_path).get_data(as_text=True))

    def test_one_tap_gap_booking_on_home_and_concept_notice_everywhere(self):
        notice = "Концепт для конкурса MGIMO × AI Challenge. Не официальный сервис вуза. Все данные вымышлены."
        self.assertIn(notice, self.browser.get("/login").get_data(as_text=True))
        self.assertIn(notice, self.browser.get("/verify/nonexistenttoken1234", follow_redirects=False).get_data(as_text=True))

        self.login()
        home_page = self.browser.get("/")
        home_html = home_page.get_data(as_text=True)
        self.assertIn(notice, home_html)
        b_date = re.search(r'name="booking_date" value="([^"]+)"', home_html)[1]
        b_slot = re.search(r'name="slot_label" value="([^"]+)"', home_html)[1]
        gap_res = self.browser.post("/campus/book-gap", data={
            "_csrf": token(home_page),
            "booking_date": b_date,
            "slot_label": b_slot,
        })
        self.assertEqual(gap_res.status_code, 303)
        self.assertIn("Проектный бокс К–1", self.browser.get("/").get_data(as_text=True))

        staff = self.app.test_client()
        self.login(staff, 2)
        self.assertIn(notice, staff.get("/staff").get_data(as_text=True))

    def test_qr_codes_decode_to_real_scannable_urls(self):
        self.login()
        # 1. Campus pass QR on /profile decodes to public /verify/pass/<token>
        prof_html = self.browser.get("/profile").get_data(as_text=True)
        pass_decoded = decode_rendered_qr(prof_html, index=0)
        self.assertIn("/verify/pass/", pass_decoded)
        anon = self.app.test_client()
        pass_verify = anon.get(urlsplit(pass_decoded).path)
        self.assertEqual(pass_verify.status_code, 200)
        self.assertIn("Семестр ID", pass_verify.get_data(as_text=True))
        self.assertIn("Маякова В. И.", pass_verify.get_data(as_text=True))

        # 2. Certificate QR on /requests/<id>/document decodes to public /verify/<token>
        reqs_page = self.browser.get("/requests")
        issued = self.browser.post("/requests/instant/study", data={
            "_csrf": token(reqs_page),
            "nonce": token(reqs_page, "nonce"),
        })
        doc_html = self.browser.get(urlsplit(issued.location).path).get_data(as_text=True)
        # index=0 on signed-in page is doc_qr (pass modal is at end of base.html)
        doc_decoded = decode_rendered_qr(doc_html, index=0)
        self.assertRegex(doc_decoded, r"^http://localhost/verify/[A-Za-z0-9_-]+$")
        self.assertEqual(anon.get(urlsplit(doc_decoded).path).status_code, 200)

        # 3. Guest pass QR on /campus decodes to public /verify/guest/<id>
        campus_page = self.browser.get("/campus")
        vdate = re.search(r'<select id="guest_date" name="visit_date">\s*<option value="([^"]+)"', campus_page.get_data(as_text=True))[1]
        self.browser.post("/campus/guest-pass", data={
            "_csrf": token(campus_page),
            "guest_name": "Маяков Илья Сергеевич",
            "visit_date": vdate,
            "location": "Студдом № 2",
        })
        campus_after = self.browser.get("/campus").get_data(as_text=True)
        guest_decoded = decode_rendered_qr(campus_after, index=0)
        self.assertIn("/verify/guest/", guest_decoded)
        guest_verify = anon.get(urlsplit(guest_decoded).path)
        self.assertEqual(guest_verify.status_code, 200)
        self.assertIn("Маяков И. С.", guest_verify.get_data(as_text=True))

    def test_navigator_honest_empty_state_without_confident_misses(self):
        self.login()
        for q in ("как перевестись на бюджет", "хочу академ", "где находится столовая"):
            html = self.browser.get(f"/navigator?q={q}").get_data(as_text=True)
            self.assertNotIn("data-nav-card", html, msg=q)
            self.assertIn("Не нашёл готового сценария", html, msg=q)
            self.assertIn("Спросить ассистента", html, msg=q)
            self.assertIn("Написать в учебный офис", html, msg=q)

        # Prefill from navigator empty state into appeal form
        appeal_html = self.browser.get("/requests/new/appeal?q=как+перевестись+на+бюджет").get_data(as_text=True)
        self.assertIn("как перевестись на бюджет", appeal_html)

    def test_reset_demo_cli_restores_seed_and_preserves_password_hashes(self):
        custom_cfg = {
            **self.config,
            "DATABASE": str(Path(self.sandbox.name) / "reset_test.sqlite3"),
            "DEMO_PASSWORDS": ("Custom-Lera-99", "Custom-Misha-99", "Custom-Dean-99"),
        }
        custom_app = create_app(custom_cfg)
        client = custom_app.test_client()
        login_res = client.post("/login", data={
            "_csrf": token(client.get("/login")),
            "email": "lera@demo.example",
            "password": "Custom-Lera-99",
        })
        self.assertEqual(login_res.status_code, 303)

        # Pollute DB with extra military certificates
        for _ in range(3):
            rp = client.get("/requests")
            client.post("/requests/instant/military", data={"_csrf": token(rp), "nonce": token(rp, "nonce")})
        self.assertGreaterEqual(client.get("/requests").get_data(as_text=True).count("Справка в военкомат (Прил. № 4)"), 4)

        # Run flask reset-demo CLI
        res = custom_app.test_cli_runner().invoke(args=["reset-demo"])
        self.assertEqual(res.exit_code, 0)
        self.assertIn("Demo data reset complete", res.output)

        # Extra certificates are gone (only Lera's 2 seeded items remain in .request-row)
        reqs_after = client.get("/requests").get_data(as_text=True)
        self.assertEqual(reqs_after.count("request-row"), 2)

        # Custom password hash from env is preserved
        client2 = custom_app.test_client()
        self.assertEqual(client2.post("/login", data={
            "_csrf": token(client2.get("/login")),
            "email": "lera@demo.example",
            "password": "Custom-Lera-99",
        }).status_code, 303)

    def test_favicon_manifest_brand_mark_and_password_toggle(self):
        # Anonymous public access to favicons, apple-touch-icon and webmanifest
        ico = self.browser.get("/favicon.ico")
        self.assertEqual(ico.status_code, 200)
        self.assertEqual(ico.data[:6], b"\x00\x00\x01\x00\x03\x00")  # ICO header with 3 sizes (16/32/48)
        ico.close()

        svg = self.browser.get("/static/favicon.svg")
        self.assertEqual(svg.status_code, 200)
        svg_text = svg.get_data(as_text=True)
        self.assertIn('viewBox="0 0 32 32"', svg_text)
        self.assertNotIn("<style", svg_text)
        svg.close()

        apple = self.browser.get("/apple-touch-icon.png")
        self.assertEqual(apple.status_code, 200)
        self.assertEqual(apple.data[:8], b"\x89PNG\r\n\x1a\n")
        apple.close()

        manifest = self.browser.get("/manifest.webmanifest")
        self.assertEqual(manifest.status_code, 200)
        m_text = manifest.get_data(as_text=True)
        self.assertIn("192x192", m_text)
        self.assertIn("512x512", m_text)
        manifest.close()

        for png_name in ("icon-192.png", "icon-512.png"):
            png_resp = self.browser.get(f"/static/{png_name}")
            self.assertEqual(png_resp.status_code, 200)
            png_resp.close()

        login_html = self.browser.get("/login").get_data(as_text=True)
        self.assertIn("brand-mark-svg", login_html)
        self.assertIn('rel="manifest"', login_html)
        self.assertIn('rel="apple-touch-icon"', login_html)
        self.assertIn('class="password-toggle"', login_html)
        self.assertNotIn('icon-btn password-toggle', login_html)
        self.assertIn('aria-label="Показать пароль"', login_html)
        self.assertIn('data-tip="Показать пароль"', login_html)


if __name__ == "__main__":
    unittest.main()
