"""Invented, repeatable demo data. Dates follow the academic week in Moscow."""
from datetime import date, datetime, time, timedelta
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
GRADES = {
    1: [
        ("Стратегический маркетинг", "Экзамен", "5", 6),
        ("Маркетинговая аналитика", "Экзамен", "4", 8),
        ("Поведение потребителей", "Зачёт", "Зачтено", 5),
        ("Методы исследований", "Зачёт", "Зачтено", 4),
        ("Дизайн продукта", "Зачёт", "", 9),
        ("Экономика фирмы", "Экзамен", "", 11),
    ],
    2: [
        ("Международная экономика", "Экзамен", "4", 6),
        ("Теория переговоров", "Зачёт", "Зачтено", 5),
        ("Международное право", "Экзамен", "5", 8),
        ("Французский язык", "Зачёт", "", 8),
        ("Региональные исследования", "Экзамен", "", 11),
    ],
}
REQUEST_TYPES = {
    "study": ("Справка об обучении", "Подтверждает, что вы учитесь в университете.", "file"),
    "grades": ("Выписка об успеваемости", "Оценки и зачёты за текущий семестр.", "layers"),
    "appeal": ("Заявление в деканат", "Опишите вопрос, по которому нужен ответ деканата.", "message"),
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


def lessons_on(group, day):
    return [
        {"day": day, "start": start, "end": end, "kind": kind, "title": title,
         "teacher": teacher, "room": room, "previous": previous,
         "id": f"lesson-{day.isoformat()}-{start.replace(':', '')}"}
        for weekday, start, end, kind, title, teacher, room, previous in TIMETABLE[group]
        if weekday == day.weekday()
    ]


def next_lesson(group, at):
    for offset in range(8):
        for item in lessons_on(group, at.date() + timedelta(days=offset)):
            if offset or time.fromisoformat(item["end"]) > at.time():
                return item
    return None


def academic_results(student, day):
    demo_start = date(2026, 11, 23)
    start = demo_start if day <= date(2026, 12, 7) else week_start(day)
    return [{"title": title, "kind": kind, "result": result,
             "date": start + timedelta(days=offset)}
            for title, kind, result, offset in GRADES[student]]


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
        "kind": "Сессия", "title": f"{checkpoint['kind']}: {checkpoint['title']}",
        "body": "Проверьте дату ближайшей контрольной точки и другие сроки сессии.",
        "date": checkpoint["date"], "icon": "clock", "link": "/grades#session-heading",
        "action": "К датам сессии",
    }
    return [
        {"id": "schedule-a" if student["id"] == 1 else "schedule-b", "kind": "Расписание",
         "title": moved["title"],
         "body": f"Аудитория изменилась с {moved['previous']} на {moved['room']}. Время прежнее, {moved['start']}.",
         "date": change_day, "icon": "arrow-swap",
         "link": f"/schedule?date={change_day.isoformat()}#{moved['id']}", "action": "К занятию",
         "old_room": moved["previous"], "new_room": moved["room"]},
        special,
        {"id": "office", "kind": "Деканат", "title": "Уточнили порядок получения справок",
         "body": "Электронные справки появятся в ваших заявках. Для бумажного экземпляра выберите получение в деканате.",
         "date": current, "icon": "file", "link": "/requests", "action": "К заявкам"},
    ]
