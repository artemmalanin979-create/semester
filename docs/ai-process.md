# Материалы процесса

## Запрос участника

«Ты занимаешь вторым проектом МГИМО x AI-CHALLENGE». К сообщению приложено полное задание «Цифровой деканат будущего».

«Кстати важно взять первое место - поэтому помаксимум добивай по критериям».

Codex связал расписание, уведомления и заявки через действия на главной, выбрал Flask с SQLite, сделал два тестовых профиля и собрал браузерные проверки.

## ImageGen

Точный отправленный промпт:

> Create one ultra-wide crop-friendly editorial architectural photograph for the web UI of a fictional Russian university student portal named Семестр. No text, signage, marks, typography, people or vehicles. One striking modernist university building in pale grey weathered concrete, sculptural large repeating fins and a high elevated walkway, photographed from low viewpoint with geometric strong diagonals and depth. Place the clearly defined architecture on the right two thirds, keep leftmost third simple and quite dark. Cool petrol teal sky and evening slate shadows, small hints of warm interior windows, controlled restrained editorial color grade. Photorealistic high-end architecture portfolio photography with genuine texture. Keep the right half readable when cropped into a square and leave breathing room on top. Landscape 3:2. No official university architecture, no landmark reproduction.

Сгенерированное изображение сохранено в WebP без EXIF. Один кадр использован в двух пропорциях, с затемнением под текст.

## Независимое ревью

Фрагмент постановки задачи субагенту:

> Независимое read-only ревью конкурсного прототипа «Семестр» […] Проверь стабильный git diff 636da23..cd5aa96. Фокус на security/auth/IDOR, SQLite transactions/перезапуск, требования задания ко всем страницам, мобильные дефекты из кода. Обязательное ядро: вход, профиль ФИО факультет направление курс группа, сегодня/неделя с переносами, оценки/зачеты/сессия, справки и заявления со статусом, новости и напоминания.

Ревьюер воспроизвёл ошибку одновременного переключения SQLite в WAL на холодном старте, а также пересчёт дат экзаменов сразу после дедлайна приёма работ. Исправления проверены холодными запусками и тестом, сравнивающим календарь 22 и 28 ноября. Добавлены ротация тестовых паролей и проверка прямого доступа к готовому документу из другого кабинета.

## Ручные этапы

Участник выбрал конкурсное задание и определил приоритет. Codex оформил проект и выполнил проверки. Перед подачей капитан добавляет опубликованные URL и созданные для жюри пароли.
