# Smart Deanery ("Умный деканат" — Option A) Design Spec

## Intent & Why
Expand the «Семестр» prototype from a basic schedule/grades viewer into a complete university one-stop digital deanery modeled after `my.itmo`, `HSE App X / ЕЛК ВШЭ`, `dorm.mgimo.ru`, and `MIT Atlas`, while fixing layout alignment and functional depth in `/staff`.

## Goals
1. **Instant Self-Service Certificates vs Reviewed Petitions (`/requests`)**:
   - Instant 1-click issuance (`ready_at = now`) with QR verification and print-ready templates for 5 registry certificates: `study` (enrollment), `military` (Приложение № 4 for military registration), `income` (6-month scholarship & payout statement), `grades` (academic transcript), `dorm_cert` (dormitory residence certificate).
   - Reviewed petitions routed to `/staff`: `medical` (095/у illness excuse), `pgas` (increased academic scholarship / financial aid), `retake` (exam retake slip), `appeal` (individual curriculum / elective change).
   - Appointment slot booking for window `А–116` (`office_slots` table) without standing in line.
2. **Finance, Dormitory Billing & Campus Services (`/campus`)**:
   - Student contracts & charges (`charges` table): monthly dormitory rent (`ОД-24/412`, `3 400 ₽` / `ОД-23/109`, `3 100 ₽`) and optional language modules.
   - 1-click demo payment (SBP 0% / Mir card) updating SQLite state immediately and generating a printable payment receipt with QR (`/campus/receipt/<charge_id>`), strictly isolated per student (`404` for non-owners).
   - Scholarship & payout schedule card (GAS, rating supplement, next payout date, 1-click income certificate).
   - Campus life: dormitory room card, instant Guest Pass QR generator (`guest_passes`), and study room / coworking booking (`room_bookings`) linked to free schedule windows.
3. **Context-Aware Smart Navigator (`/` & `/navigator`)**:
   - Deterministic, zero-external-API situation assistant personalized with the signed-in student's live database state (group, GPA/rating, upcoming exam, unpaid dorm balance, room number), answering plain-language queries and surfacing 1-click action buttons.
4. **Aligned, Full-Featured Staff Workspace (`/staff`)**:
   - Fix column header misalignment and text wrapping in `/staff`.
   - 4 structured staff sections in sidebar and mobile nav:
     - `Очередь обращений` (`/staff`): approve OR return/reject with reason (`decision` column) + 1-click reply presets + student context badges.
     - `Расписание и переносы` (`/staff?tab=schedule`): live room override creation/removal (`room_overrides` table) that immediately updates student timetables and publishes a transfer notice.
     - `Реестр студентов` (`/staff?tab=students`): live overview of student ratings, credits, dorm payment status, and pending requests.
     - `Объявления` (`/staff?tab=notices`): aligned two-column composer + published feed with delete/archive support.

## Constraints & Anti-Goals
- **Strict Visual System**: Preserve `Adwaita Sans` + `JetBrains Mono` (`.num`), calm sage-stone light theme and canonical monochrome `oklch(.17 0 0)` dark theme, zero emojis, zero ALL-CAPS eyebrows, zero pastel capsule soup, zero inline `style=` or inline `<script>` (`CSP: default-src 'self'`).
- **Responsive**: Zero horizontal overflow from `360px` to `1440px` in both themes. Student mobile `.bottom-nav` holds 5 primary tabs (`Главная`, `Пары`, `Оценки`, `Документы`, `Кампус`) while `Уведомления` and `Профиль` remain in `.topbar`.
- **Backwards Compatibility**: Keep all existing routes and `tests/test_portal.py` invariants green.
