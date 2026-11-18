"""Invented, repeatable demo data. Dates follow the academic week in Moscow."""
from datetime import date, datetime, time, timedelta
from hashlib import sha256
from zoneinfo import ZoneInfo

import segno

MOSCOW = ZoneInfo("Europe/Moscow")
MONTH = "января февраля марта апреля мая июня июля августа сентября октября ноября декабря".split()
WEEKDAY = "Понедельник Вторник Среда Четверг Пятница Суббота Воскресенье".split()
SHORT_DAY = "Пн Вт Ср Чт Пт Сб Вс".split()

STUDENTS = (
    (1, "lera@demo.example", "Валерия Маякова", "Валерия Ильинична Маякова",
     "Институт маркетинга и предпринимательства", "Маркетинг и управление продуктом", 3, "МП-24-1", "student"),
    (2, "misha@demo.example", "Михаил Ратников", "Михаил Егорович Ратников",
     "Факультет международных отношений", "Международные отношения", 4, "МО-23-2", "student"),
    (3, "dean@demo.example", "Елена Орлова", "Елена Викторовна Орлова",
     "Учебный офис деканата", "Ведущий методист · окно А–116", 0, "А–116", "staff"),
)

STUDENT_PROFILES = {
    1: {
        "card_number": "24-МП-0184",
        "degree": "Бакалавриат · очная форма",
        "funding": "Бюджетная основа",
        "languages": "Английский (C1) · Испанский (B2)",
        "advisor": "Е. В. Ларионова · каб. А–118",
        "pass_zone": "Корпуса А, Б, В · Студдом № 2 · Читальный зал",
        "pass_valid": "31 августа 2027",
        "order_no": "№ 418-ст от 26.08.2024",
        "program_code": "38.03.02 Менеджмент",
        "admission_year": 2024,
        "study_end": "31 августа 2028",
        "gender": "f",
        "funding_basis": "budget",
        "lives_in_dorm": True,
        "military_registered": False,
    },
    2: {
        "card_number": "23-МО-0412",
        "degree": "Бакалавриат · очная форма",
        "funding": "Бюджетная основа",
        "languages": "Французский (C1) · Английский (C1)",
        "advisor": "Д. А. Корсаков · каб. В–204",
        "pass_zone": "Корпуса А, Б, В · Студдом № 1 · Дипломатический зал",
        "pass_valid": "31 августа 2027",
        "order_no": "№ 392-ст от 25.08.2023",
        "program_code": "41.03.05 Международные отношения",
        "admission_year": 2023,
        "study_end": "31 августа 2027",
        "gender": "m",
        "funding_basis": "budget",
        "lives_in_dorm": True,
        "military_registered": True,
    },
    3: {
        "card_number": "ST-А116-09",
        "degree": "Сотрудник учебного офиса",
        "funding": "Будни, 10:00–17:00",
        "languages": "Корпуса А, Б, В",
        "advisor": "Приём студентов: Пн–Пт, 10:00–17:00",
        "pass_zone": "Служебный доступ · Учебный офис А–116",
        "pass_valid": "31 августа 2027",
        "order_no": "Штатный реестр",
        "program_code": "Учебный офис",
        "admission_year": 0,
        "study_end": "",
        "gender": "f",
        "funding_basis": "staff",
        "lives_in_dorm": False,
        "military_registered": False,
    },
}

DORM_INFO = {
    1: {
        "building": "Студдом № 2",
        "address": "Кампус Юго-Запад, корп. 2",
        "room": "Б–614 (двухместный блок)",
        "contract": "ОД-24/412",
        "warden": "Н. П. Громова · каб. 104",
        "monthly_rub": 3400,
        "guest_hours": "Ежедневно 09:00–22:00 по разовому QR",
    },
    2: {
        "building": "Студдом № 1",
        "address": "Кампус Запад, корп. 1",
        "room": "А–308 (двухместный номер)",
        "contract": "ОД-23/109",
        "warden": "А. С. Ветров · каб. 102",
        "monthly_rub": 3100,
        "guest_hours": "Ежедневно 09:00–22:00 по разовому QR",
    },
}

SCHOLARSHIPS = {
    1: {
        "card_mask": "Мир •• 4819",
        "next_date": "25 ноября",
        "total_monthly": 10700,
        "items": (
            ("Государственная академическая стипендия (ГАС)", 4200, "Назначена по итогам летней сессии"),
            ("Надбавка за академический рейтинг 90+", 6500, "Топ-15 % потока · осенний семестр"),
        ),
        "history": (
            ("Октябрь 2026", "ГАС + рейтинговая надбавка", 10700, "Выплачено 25.10"),
            ("Сентябрь 2026", "ГАС + рейтинговая надбавка", 10700, "Выплачено 25.09"),
            ("Август 2026", "Государственная академическая стипендия", 4200, "Выплачено 25.08"),
            ("Июль 2026", "Государственная академическая стипендия", 4200, "Выплачено 25.07"),
            ("Июнь 2026", "Государственная академическая стипендия", 4200, "Выплачено 25.06"),
            ("Май 2026", "Государственная академическая стипендия", 4200, "Выплачено 25.05"),
        ),
    },
    2: {
        "card_mask": "Мир •• 9034",
        "next_date": "25 ноября",
        "total_monthly": 4200,
        "items": (
            ("Государственная академическая стипендия (ГАС)", 4200, "Базовая ставка по итогам сессии"),
        ),
        "history": (
            ("Октябрь 2026", "Государственная академическая стипендия", 4200, "Выплачено 25.10"),
            ("Сентябрь 2026", "Государственная академическая стипендия", 4200, "Выплачено 25.09"),
            ("Август 2026", "Государственная академическая стипендия", 4200, "Выплачено 25.08"),
            ("Июль 2026", "Государственная академическая стипендия", 4200, "Выплачено 25.07"),
            ("Июнь 2026", "ГАС + проектная премия", 9200, "Выплачено 25.06"),
            ("Май 2026", "Государственная академическая стипендия", 4200, "Выплачено 25.05"),
        ),
    },
}

# id, student_id, category, title, contract_no, period_label, amount_rub, due_label, initial_status
INITIAL_CHARGES = (
    ("chg-1-nov", 1, "Общежитие", "Проживание в Студдоме № 2 (комн. Б–614)", "ОД-24/412", "Ноябрь 2026", 3400, "до 25 ноября", "unpaid"),
    ("chg-1-oct", 1, "Общежитие", "Проживание в Студдоме № 2 (комн. Б–614)", "ОД-24/412", "Октябрь 2026", 3400, "оплачено 21 октября", "paid"),
    ("chg-1-lang", 1, "Доп. модуль", "Практикум «Деловой испанский B2–C1»", "ДОП-24/88", "Осенний семестр", 14500, "оплачено 12 октября", "paid"),
    ("chg-2-nov", 2, "Общежитие", "Проживание в Студдоме № 1 (комн. А–308)", "ОД-23/109", "Ноябрь 2026", 3100, "до 25 ноября", "unpaid"),
    ("chg-2-dip", 2, "Доп. модуль", "Курс «Дипломатический перевод (французский)»", "ДОП-23/31", "Осенний семестр", 16000, "до 30 ноября", "unpaid"),
)

STUDY_SPACES = (
    ("box-k1", "Проектный бокс К–1", "Читальный зал, Корпус А, 2 этаж · 4 места · экран USB-C"),
    ("box-k2", "Переговорная К–2", "Корпус А, 2 этаж · 6 мест · маркерная стена"),
    ("media-m1", "Медиастудия М–1", "Корпус Б, 2 этаж · запись презентаций и звонков"),
    ("cw-gallery", "Коворкинг «Галерея», стол на 4", "Тёплая галерея между корпусами А и Б · розетки у каждого места"),
)

# Переговорные (закрытые комнаты под встречи) и коворкинг (открытые рабочие места) — разные подвкладки
SPACE_KIND = {
    "box-k2": "rooms",
    "media-m1": "rooms",
    "box-k1": "cowork",
    "cw-gallery": "cowork",
}

BOOKING_SLOTS = ("11:35–13:00", "13:35–15:00", "16:00–17:30", "17:30–19:00")
OFFICE_SLOT_TIMES = ("11:40", "13:40", "15:50", "16:20")

ROOMS = {
    "А–116": ("Корпус А", "1 этаж", "Учебный офис деканата, правое крыло от атриума"),
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

TEACHING_ROOMS = tuple(r for r in ROOMS if r != "А–116")

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
        (1, "14:15", "15:45", "Практика", "Методы исследований", "Л. А. Корнеева", "Б–105", ""),
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
        (1, "13:15", "14:45", "Практика", "Французский язык", "Л. Н. Савельева", "В–309", ""),
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

# Instant registry certificates (1-click PDF/QR issuance)
INSTANT_TYPES = {
    "study": (
        "Справка об обучении",
        "Подтверждает статус студента, курс, очную форму обучения и факультет.",
        "file",
    ),
    "military": (
        "Справка в военкомат (Прил. № 4)",
        "Воинский учёт и отсрочка: номер приказа о зачислении, код направления и срок окончания.",
        "shield",
    ),
    "income": (
        "Справка о стипендии и выплатах",
        "Помесячная ведомость начислений за 6 месяцев для банка, визы, соцкарты или вычета.",
        "wallet",
    ),
    "grades": (
        "Выписка об успеваемости",
        "Дисциплины, зачётные единицы (ЗЕТ) и 100-балльный рейтинг за семестр.",
        "layers",
    ),
    "dorm_cert": (
        "Справка о проживании в общежитии",
        "Подтверждение договора найма, корпуса и комнаты в студенческом доме.",
        "home",
    ),
}

# Reviewed petitions routed to the Dean's Office queue (/staff)
PETITION_TYPES = {
    "medical": (
        "Медсправка о болезни (095/у)",
        "Закрытие пропусков занятий и перенос контрольных точек по уважительной причине.",
        "clock",
    ),
    "pgas": (
        "Заявка на ПГАС / матпомощь",
        "Конкурс на повышенную академическую стипендию или разовая социальная поддержка.",
        "chart",
    ),
    "retake": (
        "Направление на пересдачу",
        "Запрос электронного экзаменационного листа («бегунка») на пересдачу или добор баллов.",
        "refresh",
    ),
    "appeal": (
        "Заявление в учебный офис",
        "Индивидуальный учебный план, смена факультатива, второго языка или перезачёт.",
        "message",
    ),
}

REQUEST_TYPES = {**INSTANT_TYPES, **PETITION_TYPES}


def eligibility(student_id):
    """Profile rules: which services make sense for this student (no guesses from chat)."""
    meta = STUDENT_PROFILES.get(student_id, {})
    is_student = meta.get("funding_basis") in {"budget", "contract"}
    military = bool(is_student and meta.get("gender") == "m" and meta.get("military_registered"))
    scholarship = bool(is_student and meta.get("funding_basis") == "budget" and student_id in SCHOLARSHIPS)
    dorm = bool(is_student and meta.get("lives_in_dorm") and student_id in DORM_INFO)
    return {"military": military, "scholarship": scholarship, "dorm": dorm}


# Instant certificate kind -> eligibility flag that must be true (None = available to every student)
INSTANT_RULES = {"study": None, "grades": None, "military": "military", "income": "scholarship", "dorm_cert": "dorm"}


def instant_types_for(student_id):
    rules = eligibility(student_id)
    return {
        kind: spec for kind, spec in INSTANT_TYPES.items()
        if INSTANT_RULES[kind] is None or rules[INSTANT_RULES[kind]]
    }

STAFF_PRESETS = (
    "Согласовано учебным офисом. Изменения отражены в карточке студента.",
    "Пропуски по медицинской справке закрыты, перенос аттестации согласован.",
    "Достижения приняты к конкурсу на ПГАС в осеннем семестре.",
    "Возвращено на доработку: уточните период и реквизиты подтверждающего документа.",
    "Отклонено: не приложено основание, предусмотренное учебным регламентом.",
)

PREFILL_TEMPLATES = {
    "medical": ("Форма 095/у", "Освобождение от учебных занятий по медицинской справке 095/у (поликлиника № 209), прошу перенести контрольную точку на резервный день."),
    "pgas": ("ПГАС · учебная деятельность", "Прошу включить анкету в конкурс на повышенную государственную академическую стипендию по итогам семестрового рейтинга и проектной работы."),
    "missed": ("Объяснительная по пропуску занятия", "Прошу учесть уважительную причину пропуска семинара (участие в выездном кейс-этапе от факультета) и разрешить отработку темы."),
    "curriculum": ("Индивидуальный учебный план", "Прошу согласовать включение профильного факультатива в индивидуальный учебный план осеннего семестра."),
}


def mask_full_name(full_name):
    """Mask 'Валерия Ильинична Маякова' or 'Маяков Илья Сергеевич' -> 'Маякова В. И.' / 'Маяков И. С.'."""
    parts = [p for p in (full_name or "").split() if p]
    if len(parts) >= 3:
        patronymic_endings = ("ович", "евич", "ична", "овна", "евна", "ич", "кызы", "оглы")
        if parts[-1].lower().endswith(patronymic_endings):
            return f"{parts[0]} {parts[1][0]}. {parts[2][0]}."
        return f"{parts[-1]} {parts[0][0]}. {parts[1][0]}."
    if len(parts) == 2:
        return f"{parts[-1]} {parts[0][0]}."
    return parts[0] if parts else "Обучающийся"


def fmt_rub(amount):
    return f"{amount:,}".replace(",", " ") + " ₽"


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


def lessons_on(group, day, overrides=None):
    slot_lookup = {start: idx + 1 for idx, (start, _, _) in enumerate(GROUP_SLOTS[group])}
    items = []
    for weekday, start, end, kind, title, teacher, room, previous in TIMETABLE[group]:
        if weekday != day.weekday():
            continue
        if overrides and (weekday, start) in overrides:
            new_room = overrides[(weekday, start)]
            if new_room != room:
                previous = previous or room
                room = new_room
        wing, floor, nav_hint = ROOMS.get(room, ("Кампус", "1 этаж", ""))
        prev_wing = ROOMS.get(previous, ("", "", ""))[0] if previous else ""
        items.append({
            "day": day,
            "weekday": weekday,
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
    """Map lesson id -> concise transition or bookable free-window note shown after that lesson."""
    hints = {}
    has_window = False
    for idx in range(len(lessons) - 1):
        curr_item = lessons[idx]
        next_item = lessons[idx + 1]
        gap = _minutes(next_item["start"]) - _minutes(curr_item["end"])
        if gap >= 60:
            has_window = True
            hours, mins = divmod(gap, 60)
            span = f"{hours} ч {mins} мин" if mins else f"{hours} ч"
            slot_lbl = "11:35–13:00" if _minutes(curr_item["end"]) <= 11 * 60 + 35 else "13:35–15:00"
            note = (
                f"Свободное окно {curr_item['end']}–{next_item['start']} — можно забрать оригинал в А–116 или занять бокс"
                if has_ready_office_doc
                else f"Свободное окно {curr_item['end']}–{next_item['start']} — проектный бокс К–1 свободен"
            )
            hints[curr_item["id"]] = {
                "kind": "window",
                "badge": f"Окно {span}",
                "text": note,
                "cta_campus": True,
                "book_slot": slot_lbl,
                "book_date": curr_item["day"].isoformat(),
            }
        elif curr_item["wing"] != next_item["wing"]:
            hints[curr_item["id"]] = {
                "kind": "route",
                "badge": f"Перерыв {gap} мин",
                "text": f"{curr_item['wing']} → {next_item['wing']} по галерее 2 этажа (~4 мин)",
                "cta_campus": False,
                "book_slot": "",
                "book_date": "",
            }
    if lessons and not has_window:
        last = lessons[-1]
        last_end = _minutes(last["end"])
        slot_lbl = "13:35–15:00" if last_end <= 13 * 60 + 35 else "16:00–17:30"
        hints[last["id"]] = {
            "kind": "window",
            "badge": f"Свободно с {last['end']}",
            "text": (
                "После пар можно забрать готовую справку в А–116 или занять бокс коворкинга"
                if has_ready_office_doc
                else "Окно для командной работы после аудиторных пар"
            ),
            "cta_campus": True,
            "book_slot": slot_lbl,
            "book_date": last["day"].isoformat(),
        }
    return hints


def next_lesson(group, at, overrides=None):
    for offset in range(8):
        for item in lessons_on(group, at.date() + timedelta(days=offset), overrides=overrides):
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


_CERT_SHORT = {
    "study": "об обучении",
    "military": "в военкомат, Прил. № 4",
    "income": "о стипендии",
    "grades": "выписка оценок",
    "dorm_cert": "о проживании",
}


def notices(student, stamp, overrides=None):
    current = stamp.date()
    group = student["student_group"]
    change_day = week_start(current)
    if current.weekday() > 0 or stamp.strftime("%H:%M") >= ("13:30" if student["id"] == 1 else "12:30"):
        change_day += timedelta(days=7)
    day_items = lessons_on(group, change_day, overrides=overrides)
    moved = next((item for item in day_items if item["previous"]), day_items[0])
    checkpoint = min(
        (row for row in academic_results(student["id"], current) if not row["result"]),
        key=lambda row: row["date"],
    )
    special = {
        "id": "deadline-a" if student["id"] == 1 else "deadline-b",
        "kind": "Сессия",
        "title": f"{checkpoint['kind']}: {checkpoint['title']}",
        "body": (
            f"Назначен на {fmt_date(checkpoint['date'])} в {checkpoint['exam_time']}, "
            f"аудитория {checkpoint['exam_room']}. Семестровый допуск — {checkpoint['score']} из 100."
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
                f"Аудитория изменена с {moved['previous']} на {moved['room']} ({moved['wing']}, {moved['floor']}). "
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
            "title": "Мгновенные справки и запись в окно А–116",
            "body": (
                f"Типовые справки ({', '.join(_CERT_SHORT[k] for k in instant_types_for(student['id']))}) выпускаются онлайн за 1 секунду. "
                "Для бумажных оригиналов доступна запись по слотам."
            ),
            "date": current,
            "icon": "file",
            "link": "/requests?tab=order",
            "action": "К документам",
        },
    ]


def qr_svg_path(payload_text):
    """Encode payload_text as a real ISO/IEC 18004 scannable QR matrix via segno."""
    qr = segno.make(payload_text, error="m", boost_error=False)
    matrix = qr.matrix
    n = len(matrix)
    border = 4
    total = n + 2 * border
    parts = []
    for r, row in enumerate(matrix):
        y = r + border
        c = 0
        while c < n:
            if row[c]:
                start = c
                while c < n and row[c]:
                    c += 1
                parts.append(f"M{start + border} {y}h{c - start}v1h-{c - start}z")
            else:
                c += 1
    return {"dim": total, "path": "".join(parts), "url": payload_text}


def build_week_ics(student, start_day, overrides=None):
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
        for item in lessons_on(student["student_group"], day, overrides=overrides):
            dt_start = f"{day:%Y%m%d}T{item['start'].replace(':', '')}00"
            dt_end = f"{day:%Y%m%d}T{item['end'].replace(':', '')}00"
            note = f"{item['kind']} · Преподаватель: {item['teacher']}"
            if item["previous"]:
                note += f" (Перенос из {item['previous']})"
            lines.extend([
                "BEGIN:VEVENT",
                f"UID:{item['id']}-{student['student_group']}@semester.demo",
                "DTSTAMP:" + stamp_utc,
                f"DTSTART;TZID=Europe/Moscow:{dt_start}",
                f"DTEND;TZID=Europe/Moscow:{dt_end}",
                f"SUMMARY:{item['title']} ({item['kind']})",
                f"LOCATION:{item['room']}, {item['wing']}",
                f"DESCRIPTION:{note}",
                "END:VEVENT",
            ])
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"
