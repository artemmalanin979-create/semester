"""Согласованность вымышленных сид-данных: пол, курс, основа обучения, общежитие, воинский учёт."""
import re
from datetime import date

from semester.demo import (
    DORM_INFO,
    INITIAL_CHARGES,
    INSTANT_RULES,
    INSTANT_TYPES,
    SCHOLARSHIPS,
    SPACE_KIND,
    STUDENT_PROFILES,
    STUDENTS,
    STUDY_SPACES,
    eligibility,
    instant_types_for,
)

TODAY = date(2026, 11, 17)


def students():
    return [row for row in STUDENTS if row[8] == "student"]


def test_course_matches_admission_year_and_group_code():
    for sid, _email, _name, _full, _fac, _prog, course, group, _role in students():
        meta = STUDENT_PROFILES[sid]
        admission = meta["admission_year"]
        academic_year_start = TODAY.year if TODAY.month >= 9 else TODAY.year - 1
        assert course == academic_year_start - admission + 1, sid
        assert group.split("-")[1] == str(admission)[2:], sid
        assert meta["card_number"].startswith(str(admission)[2:]), sid
        assert str(admission) in meta["order_no"], sid
        assert int(meta["study_end"][-4:]) == admission + 4  # 4-year bachelor


def test_military_certificate_only_for_registered_male_students():
    for sid, *_ in students():
        meta = STUDENT_PROFILES[sid]
        allowed = "military" in instant_types_for(sid)
        assert allowed == (meta["gender"] == "m" and meta["military_registered"]), sid
    assert "military" not in instant_types_for(1)  # Лера: не на воинском учёте
    assert "military" in instant_types_for(2)


def test_scholarship_only_for_budget_students_and_dorm_only_for_residents():
    for sid, *_ in students():
        meta = STUDENT_PROFILES[sid]
        rules = eligibility(sid)
        assert rules["scholarship"] == (meta["funding_basis"] == "budget")
        if meta["funding_basis"] != "budget":
            assert "income" not in instant_types_for(sid)
        if not meta["lives_in_dorm"]:
            assert "dorm_cert" not in instant_types_for(sid)
            assert not [c for c in INITIAL_CHARGES if c[1] == sid and c[2] == "Общежитие"]
        else:
            assert sid in DORM_INFO
            dorm_charges = [c for c in INITIAL_CHARGES if c[1] == sid and c[2] == "Общежитие"]
            assert all(DORM_INFO[sid]["contract"] == c[4] for c in dorm_charges)
            assert all(DORM_INFO[sid]["monthly_rub"] == c[6] for c in dorm_charges)
        if rules["scholarship"]:
            sch = SCHOLARSHIPS[sid]
            assert sch["total_monthly"] == sum(item[1] for item in sch["items"])


def test_rating_bonus_matches_grades_and_staff_has_no_student_services():
    from semester.demo import GRADES

    for sid, *_ in students():
        scores = [row[4] for row in GRADES[sid]]
        has_bonus = any("90+" in item[0] for item in SCHOLARSHIPS[sid]["items"])
        assert has_bonus == (sum(scores) / len(scores) >= 90), sid
        assert not any(row[2] == "3" for row in GRADES[sid])  # ГАС не платится при тройках
    assert eligibility(3) == {"military": False, "scholarship": False, "dorm": False}


def test_every_instant_rule_and_space_kind_is_defined():
    assert set(INSTANT_RULES) == set(INSTANT_TYPES)
    assert {sp[0] for sp in STUDY_SPACES} == set(SPACE_KIND)
    assert set(SPACE_KIND.values()) == {"rooms", "cowork"}


def test_templates_do_not_hardcode_military_for_everyone():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "semester" / "templates"
    for name in ("home.html", "base.html", "requests.html", "finance.html", "dorm.html"):
        text = (root / name).read_text(encoding="utf-8")
        assert not re.search(r"военкомат", text, re.I), name


def test_login_cards_and_local_demo_accounts_match_student_courses(tmp_path):
    from pathlib import Path
    from semester import LOCAL_DEMO_ACCOUNTS, create_app

    by_email = {row[1]: row for row in students()}
    for acc in LOCAL_DEMO_ACCOUNTS:
        if acc["email"] in by_email:
            expected_course = by_email[acc["email"]][6]
            assert f"{expected_course} курс" in acc["track"], acc

    prod_app = create_app({
        "TESTING": True,
        "SECRET_KEY": "prod-check-secret-01234567890123456789",
        "DATABASE": str(tmp_path / "prod_login.sqlite3"),
        "DEMO_PASSWORDS": ("DemoPass-Lera-26", "DemoPass-Misha-26", "DemoPass-Dean-26"),
    })
    login_html = prod_app.test_client().get("/login").get_data(as_text=True)
    assert "lera@demo.example · Маркетинг, 3 курс" in login_html
    assert "misha@demo.example · МО, 4 курс" in login_html
    assert 'data-demo-password="DemoPass-Lera-26"' in login_html
    assert 'data-demo-password="DemoPass-Misha-26"' in login_html
    assert 'data-demo-password="DemoPass-Dean-26"' in login_html
    assert "автоматически сбрасываются каждые 45 минут" in login_html

    app = create_app({
        "TESTING": True,
        "SECRET_KEY": "font-check-secret-0123456789",
        "DATABASE": str(tmp_path / "font_check.sqlite3"),
    })
    client = app.test_client()
    for fname in ("InterDisplay-SemiBold.woff2", "InterDisplay-Bold.woff2", "OFL-InterDisplay.txt"):
        r = client.get(f"/static/{fname}")
        assert r.status_code == 200, fname
        r.close()
