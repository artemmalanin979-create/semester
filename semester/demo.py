"""Invented, repeatable demo data. Dates follow the academic week in Moscow."""
from datetime import date, datetime, time, timedelta
from hashlib import sha256
from zoneinfo import ZoneInfo

MOSCOW = ZoneInfo("Europe/Moscow")
MONTH = "января февраля марта апреля мая июня июля августа сентября октября ноября декабря".split()
WEEKDAY = "Понедельник Вторник Среда Четверг Пятница Суббота Воскресенье".split()
SHORT_DAY = "Пн Вт Ср Чт Пт Сб Вс".split()

STUDENTS = (
    (1, "lera@demo.example", "Валерия Маякова", "Валерия Ильинична Маякова",
     "Институт маркетинга и предпринимательства", "Маркетинг и управление продуктом", 2, "МП-24-1"),
    (2, "misha@demo.example", "Михаил Ратников", "Михаил Егорович Ратников",
     "Факультет международных отношений", "Международные отношения", 3, "МО-23-2"),
)

STUDENT_PROFILES = {
    1: {
        "card_number": "24-МП-0184",
        "degree": "Бакалавриат · очная форма",
        "funding": "Бюджетная основа",
        "languages": "Английский (C1) · Испанский (B2)",
        "advisor": "Е. В. Ларионова · каб. А–118",
        "pass_zone": "Корпуса А, Б, В · Читальный зал · Лаборатории",
        "pass_valid": "31 августа 2027",
    },
    2: {
        "card_number": "23-МО-0412",
        "degree": "Бакалавриат · очная форма",
        "funding": "Бюджетная основа",
        "languages": "Французский (C1) · Английский (C1)",
        "advisor": "Д. А. Корсаков · каб. В–204",
        "pass_zone": "Корпуса А, Б, В · Дипломатический читальный зал",
        "pass_valid": "31 августа 2027",
    },
}

ROOMS = {
    "А–116": ("Корпус А", "1 этаж", "Сервисный центр деканата, правое крыло от атриума"),
    "А–201": ("Корпус А", "2 этаж", "Северная лестница у атриума"),
    "А–204": ("Корпус А", "2 этаж", "Северная лестница у атриума"),
    "А–220": ("Корпус А", "2 этаж", "Восточное крыло, зал семинаров"),
    "А–302": ("Корпус А", "3 этаж", "Лекционный амфитеатр у центрального лифта"),
    "А–416": ("Корпус А", "4 этаж", "Лингафонный кабинет восточного крыла"),
    "Б–105": ("Корпус Б", "1 этаж", "Компьютерный практикум у входа со двора"),
    "Б–301": ("Корпус Б", "3 этаж", "Большая потоковая аудитория"),
    "Б–302": ("Корпус Б", "3 этаж", "Малый лекционный зал"),
    "Б–408": ("Корпус Б", "4 этаж", "Переход из корпуса А по тёплой галерее 2 этажа"),
    "Б–411": ("Корпус Б", "4 этаж", "Зал региональных семинаров"),
    "В–213": ("Корпус В", "2 этаж", "Кабинет переговорных практикумов"),
    "В–303": ("Корпус В", "3 этаж", "Лекционный зал западного крыла"),
    "В–309": ("Корпус В", "3 этаж", "Языковая студия романских кафедр"),
    "В–412": ("Корпус В", "4 этаж", "Подъём на лифте западного холла корпуса В"),
    "Лаборатория 3": ("Корпус Б", "2 этаж", "Проектный медиаблок рядом с галереей"),
}

KIND_SLUGS = {
    "Лекция": "lecture",
    "Семинар": "seminar",
    "Практика": "lab",
}

GROUP_SLOTS = {
    "МП-24-1": (
        ("10:00", "11:30", "1 пара"),
        ("12:00", "13:30", "2 пара"),
        ("14:15", "15:45", "3 пара"),
    ),
    "МО-23-2": (
        ("09:00", "10:30", "1 пара"),
        ("11:00", "12:30", "2 пара"),
        ("13:15", "14:45", "3 пара"),
    ),
}

# Weekly timetable rows: weekday, start, end, type, subject, teacher, room, previous room.
TIMETABLE = {
    "МП-24-1": [
        (0, "10:00", "11:30", "Лекция", "Стратегический маркетинг", "А. Д. Соколова", "А–302", ""),
        (0, "12:00", "13:30", "Семинар", "Маркетинговая аналитика", "Р. К. Белецкий", "Б–408", "А–204"),
        (0, "14:15", "15:45", "Практика", "Дизайн продукта", "Ю. В. Сафронова", "Лаборатория 3", ""),
        (1, "10:00", "11:30", "Семинар", "Экономика фирмы", "И. Н. Грачёв", "А–201", ""),
        (1, "12:00", "13:30", "Практика", "Методы исследований", "Л. А. Корнеева", "Б–105", ""),
        (2, "10:00", "11:30", "Лекция", "Поведение потребителей", "С. Л. Дроздова", "Б–301", ""),
        (2, "12:00", "13:30", "Практика", "Дизайн продукта", "Ю. В. Сафронова", "Лаборатория 3", ""),
        (3, "10:00", "11:30", "Семинар", "Английский язык", "М. С. Ладыгина", "А–416", ""),
        (3, "14:15", "15:45", "Лекция", "Маркетинговая аналитика", "Р. К. Белецкий", "Б–302", ""),
        (4, "10:00", "11:30", "Практика", "Методы исследований", "Л. А. Корнеева", "Б–105", ""),
        (4, "12:00", "13:30", "Семинар", "Стратегический маркетинг", "А. Д. Соколова", "А–302", ""),
    ],
    "МО-23-2": [
        (0, "09:00", "10:30", "Лекция", "Международная экономика", "М. О. Кленов", "В–303", ""),
        (0, "11:00", "12:30", "Семинар", "Теория переговоров", "С. Ю. Рудова", "В–412", "В–213"),
        (0, "13:15", "14:45", "Практика", "Французский язык", "Л. Н. Савельева", "В–309", ""),
        (1, "09:00", "10:30", "Лекция", "Региональные исследования", "В. Т. Мельник", "Б–411", ""),
        (2, "11:00", "12:30", "Семинар", "Международное право", "П. С. Гранов", "А–220", ""),
        (3, "09:00", "10:30", "Практика", "Французский язык", "Л. Н. Савельева", "В–309", ""),
        (3, "11:00", "12:30", "Семинар", "Теория переговоров", "С. Ю. Рудова", "В–213", ""),
        (4, "11:00", "12:30", "Лекция", "Международная экономика", "М. О. Кленов", "В–303", ""),
        (4, "13:15", "14:45", "Семинар", "Региональные исследования", "В. Т. Мельник", "Б–411", ""),
    ],
}

# Discipline rows: title, kind, result, day_offset, rating_100, ects, credits, teacher, exam_room, exam_time
GRADES = {
    1: [
        ("Стратегический маркетинг", "Экзамен", "5", 6, 95, "A", 5, "А. Д. Соколова", "А–302", "10:00"),
        ("Маркетинговая аналитика", "Экзамен", "4", 8, 84, "B", 5, "Р. К. Белецкий", "Б–408", "12:00"),
        ("Поведение потребителей", "Зачёт", "Зачтено", 5, 92, "A", 3, "С. Л. Дроздова", "Б–301", "10:00"),
        ("Методы исследований", "Зачёт", "Зачтено", 4, 91, "A", 3, "Л. А. Корнеева", "Б–105", "11:30"),
        ("Дизайн продукта", "Зачёт", "", 9, 92, "Допуск", 4, "Ю. В. Сафронова", "Лаборатория 3", "11:00"),
        ("Экономика фирмы", "Экзамен", "", 11, 88, "Допуск", 5, "И. Н. Грачёв", "А–201", "10:00"),
    ],
    2: [
        ("Международная экономика", "Экзамен", "4", 6, 83, "B", 5, "М. О. Кленов", "В–303", "09:30"),
        ("Теория переговоров", "Зачёт", "Зачтено", 5, 93, "A", 4, "С. Ю. Рудова", "В–412", "11:00"),
        ("Международное право", "Экзамен", "5", 8, 96, "A", 6, "П. С. Гранов", "А–220", "10:00"),
        ("Французский язык", "Зачёт", "", 8, 89, "Допуск", 5, "Л. Н. Савельева", "В–309", "10:00"),
        ("Региональные исследования", "Экзамен", "", 11, 85, "Допуск", 5, "В. Т. Мельник", "Б–411", "11:30"),
    ],
}

REQUEST_TYPES = {
    "study": ("Справка об обучении", "Подтверждает статус студента, курс, форму обучения и факультет.", "file"),
    "grades": ("Выписка об успеваемости", "Дисциплины, зачётные единицы и 100-балльный рейтинг за семестр.", "layers"),
    "appeal": ("Заявление в деканат", "Свободное обращение методисту по учебному плану, расписанию или сессии.", "message"),
}


def now():
    return datetime.now(MOSCOW)


def fmt_date(day):
    return f"{day.day} {MONTH[day.month - 1]}"


def timestamp_day(value):
    return datetime.fromtimestamp(value, MOSCOW).date()


def fmt_dt(value):
    stamp = datetime.fromtimestamp(value, MOSCOW)
    return f"{fmt_date(stamp)}, {stamp:%H:%M}"


def week_start(day):
    return day - timedelta(days=day.weekday())


def academic_week_number(day):
    autumn_anchor = date(day.year if day.month >= 9 else day.year - 1, 9, 1)
    first_monday = week_start(autumn_anchor)
    return max(1, min(18, ((week_start(day) - first_monday).days // 7) + 1))


def _minutes(hhmm):
    hours, mins = map(int, hhmm.split(":"))
    return hours * 60 + mins


def lessons_on(group, day):
    slot_lookup = {start: idx + 1 for idx, (start, _, _) in enumerate(GROUP_SLOTS[group])}
    items = []
    for weekday, start, end, kind, title, teacher, room, previous in TIMETABLE[group]:
        if weekday != day.weekday():
            continue
        wing, floor, nav_hint = ROOMS.get(room, ("Кампус", "1 этаж", ""))
        prev_wing = ROOMS.get(previous, ("", "", ""))[0] if previous else ""
        items.append({
            "day": day,
            "start": start,
            "end": end,
            "kind": kind,
            "kind_slug": KIND_SLUGS.get(kind, "lecture"),
            "title": title,
            "teacher": teacher,
            "room": room,
            "previous": previous,
            "wing": wing,
            "floor": floor,
            "nav_hint": nav_hint,
            "cross_wing": bool(previous and prev_wing and prev_wing != wing),
            "slot": slot_lookup.get(start, 1),
            "id": f"lesson-{day.isoformat()}-{start.replace(':', '')}",
        })
    return items


def day_gaps(lessons, has_ready_office_doc=False):
    """Map lesson index -> smart transition or window hint shown after that lesson."""
    hints = {}
    for idx in range(len(lessons) - 1):
        curr_item = lessons[idx]
        next_item = lessons[idx + 1]
        gap = _minutes(next_item["start"]) - _minutes(curr_item["end"])
        if gap >= 60:
            hours, mins = divmod(gap, 60)
            span = f"{hours} ч {mins} мин" if mins else f"{hours} ч"
            if has_ready_office_doc:
                note = "Успеете забрать готовую справку в деканате (каб. А–116)"
            else:
                note = "Читальный зал корпуса А или проектная зона открыты"
            hints[curr_item["id"]] = {
                "kind": "window",
                "badge": f"Окно {span}",
                "text": note,
            }
        elif curr_item["wing"] != next_item["wing"]:
            hints[curr_item["id"]] = {
                "kind": "route",
                "badge": f"Перерыв {gap} мин · смена корпуса",
                "text": f"{curr_item['wing']} → {next_item['wing']}: переход по тёплой галерее 2 этажа (~4 мин)",
            }
    if lessons and has_ready_office_doc and _minutes(lessons[-1]["end"]) <= 16 * 60 + 30:
        last_id = lessons[-1]["id"]
        if last_id not in hints:
            hints[last_id] = {
                "kind": "office",
                "badge": "После пар до 17:00",
                "text": "В кабинете А–116 вас ждёт готовый бумажный экземпляр справки",
            }
    return hints


def next_lesson(group, at):
    for offset in range(8):
        for item in lessons_on(group, at.date() + timedelta(days=offset)):
            if offset or time.fromisoformat(item["end"]) > at.time():
                return item
    return None


def academic_results(student, day):
    demo_start = date(2026, 11, 23)
    start = demo_start if day <= date(2026, 12, 7) else week_start(day)
    return [
        {
            "title": title,
            "kind": kind,
            "result": result,
            "date": start + timedelta(days=offset),
            "score": score,
            "ects": ects,
            "credits": credits,
            "teacher": teacher,
            "exam_room": exam_room,
            "exam_time": exam_time,
        }
        for title, kind, result, offset, score, ects, credits, teacher, exam_room, exam_time in GRADES[student]
    ]


def notices(student, stamp):
    current = stamp.date()
    group = student["student_group"]
    change_day = week_start(current)
    if current.weekday() > 0 or stamp.strftime("%H:%M") >= ("13:30" if student["id"] == 1 else "12:30"):
        change_day += timedelta(days=7)
    moved = next(item for item in lessons_on(group, change_day) if item["previous"])
    checkpoint = min(
        (row for row in academic_results(student["id"], current) if not row["result"]),
        key=lambda row: row["date"],
    )
    special = {
        "id": "deadline-a" if student["id"] == 1 else "deadline-b",
        "kind": "Сессия",
        "title": f"{checkpoint['kind']}: {checkpoint['title']}",
        "body": (
            f"Ближайшая контрольная точка назначена на {fmt_date(checkpoint['date'])} "
            f"в {checkpoint['exam_time']}, аудитория {checkpoint['exam_room']}. "
            f"Текущий семестровый допуск — {checkpoint['score']} из 100 баллов."
        ),
        "date": checkpoint["date"],
        "icon": "clock",
        "link": "/grades#session-heading",
        "action": "К датам сессии",
    }
    return [
        {
            "id": "schedule-a" if student["id"] == 1 else "schedule-b",
            "kind": "Расписание",
            "title": moved["title"],
            "body": (
                f"Аудитория изменилась с {moved['previous']} на {moved['room']} ({moved['wing']}, {moved['floor']}). "
                f"Время прежнее, {moved['start']}–{moved['end']}."
            ),
            "date": change_day,
            "icon": "arrow-swap",
            "link": f"/schedule?date={change_day.isoformat()}#{moved['id']}",
            "action": "К занятию",
            "old_room": moved["previous"],
            "new_room": moved["room"],
        },
        special,
        {
            "id": "office",
            "kind": "Деканат",
            "title": "Электронные справки и режим работы окна А–116",
            "body": (
                "Цифровые справки формируются с проверочным кодом в разделе заявок. "
                "Бумажные оригиналы с печатью выдаются в кабинете А–116 по будням с 10:00 до 17:00."
            ),
            "date": current,
            "icon": "file",
            "link": "/requests",
            "action": "К заявкам",
        },
    ]


def qr_svg_path(seed_text):
    """Build a crisp deterministic 21x21 QR-like matrix path for campus pass & certificate verification."""
    size = 21
    digest = sha256(seed_text.encode("utf-8")).digest()
    bits = "".join(f"{byte:08b}" for byte in digest * 3)
    bit_idx = 0

    def finder(r, c, top, left):
        lr, lc = r - top, c - left
        if 0 <= lr < 7 and 0 <= lc < 7:
            if lr in (0, 6) or lc in (0, 6):
                return True
            if 2 <= lr <= 4 and 2 <= lc <= 4:
                return True
            return False
        return None

    parts = []
    for r in range(size):
        for c in range(size):
            # Quiet separator ring around the three 7x7 finder patterns
            if (r == 7 and c < 8) or (c == 7 and r < 8):
                continue
            if (r == 7 and c >= 13) or (c == 13 and r < 8):
                continue
            if (r == 13 and c < 8) or (c == 7 and r >= 13):
                continue

            val = finder(r, c, 0, 0)
            if val is None:
                val = finder(r, c, 0, 14)
            if val is None:
                val = finder(r, c, 14, 0)
            if val is None:
                if r == 6 or c == 6:
                    val = (r + c) % 2 == 0
                else:
                    val = bits[bit_idx] == "1"
                    bit_idx += 1
            if val:
                parts.append(f"M{c} {r}h1v1h-1z")
    return "".join(parts)


def build_week_ics(student, start_day):
    """Generate RFC 5545 iCalendar payload for the student's academic week."""
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Semestr Digital Deanery//MGIMO AI-Challenge//RU",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:Семестр · {student['student_group']}",
        "X-WR-TIMEZONE:Europe/Moscow",
    ]
    stamp_utc = datetime.now(ZoneInfo("UTC")).strftime("%Y%m%dT%H%M%SZ")
    for offset in range(7):
        day = start_day + timedelta(days=offset)
        for item in lessons_on(student["student_group"], day):
            dt_start = f"{day:%Y%m%d}T{item['start'].replace(':', '')}00"
            dt_end = f"{day:%Y%m%d}T{item['end'].replace(':', '')}00"
            note = f"{item['kind']} · Преподаватель: {item['teacher']}"
            if item["previous"]:
                note += f" (Перенос из {item['previous']})"
            lines.extend([
                "BEGIN:VEVENT",
                f"UID:{item['id']}-{student['student_group']}@semester.demo",
                f"DTSTAMP:{stamp_utc}",
                f"DTSTART;TZID=Europe/Moscow:{dt_start}",
                f"DTEND;TZID=Europe/Moscow:{dt_end}",
                f"SUMMARY:{item['title']} ({item['kind']})",
                f"LOCATION:{item['room']}, {item['wing']}",
                f"DESCRIPTION:{note}",
                "END:VEVENT",
            ])
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"
