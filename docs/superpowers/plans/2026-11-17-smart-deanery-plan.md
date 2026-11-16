# Smart Deanery (Option A) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the complete Option A Smart Deanery expansion (instant certificates, dorm billing & receipts, scholarships, guest passes, coworking booking, personalized situation navigator, and 4-tab aligned `/staff` workspace with live timetable overrides).

**Architecture:** Extend the Flask + SQLite (WAL) application with normalized tables (`charges`, `guest_passes`, `room_bookings`, `office_slots`, `room_overrides`, plus `decision`/`meta` on `requests`), deterministic personalized navigator logic in `semester/demo.py`, strict owner/role checks in `semester/__init__.py`, and CSP-clean Jinja2 templates styled on the monochrome `oklch` system.

**Tech Stack:** Python 3.14, Flask 3.1, SQLite 3 (WAL), Gunicorn, Playwright + Google Chrome, Unittest.

**Spec:** `docs/superpowers/specs/2026-11-17-smart-deanery-design.md`

## Global Constraints
- `Content-Security-Policy: default-src 'self'`: zero `style=` attributes and zero inline `<script>` tags in HTML or runtime JS.
- Strict owner isolation: accessing another student's request, document, payment receipt, guest pass, or `/staff` returns `404`.
- Responsive layout: `scrollWidth <= clientWidth` at `360px`, `1228px`, and `1440px` in Light and Dark themes.
- Git commits: logical commits, never include `Co-Authored-By`.

## Review Focus
1. Double-submitting a dorm payment (`POST /campus/pay/<id>`) must be idempotent and never error or double-charge.
2. Another student requesting `/campus/receipt/<charge_id>` or revoking someone else's guest pass/booking must receive `404`.
3. Returning/rejecting a student petition in `/staff` (`decision='returned'`) without a comment must provide a clear default or validation message and render `Возвращено` (`err` state) instead of unlocking a certificate document.
4. Staff setting a `room_override` for `МП-24-1` must update `lessons_on()` and `.ics` export for `МП-24-1` without affecting `МО-23-2`.
5. Mobile `360px` navigation with 6 student sections and 4 staff tabs must have zero horizontal overflow and zero truncated labels.

---

### Task 1: Schema, Demo Domain Data & Personalized Smart Navigator
**Files:**
- Modify: `semester/demo.py`
- Modify: `semester/db.py`
- Test: `tests/test_portal.py`

- [x] Add expanded certificate & petition types (`study`, `military`, `income`, `grades`, `dorm_cert`, `medical`, `pgas`, `retake`, `appeal`), scholarship breakdowns, coworking rooms, office appointment slots, and `smart_navigator_cards(student, snap, unpaid_charges, next_item)` + `answer_navigator_query(query, ...)` in `semester/demo.py`.
- [x] Extend `SCHEMA` and `_ensure_columns` in `semester/db.py` with `decision` on `requests`, plus tables `charges`, `guest_passes`, `room_bookings`, `office_slots`, and `room_overrides`, seeded idempotently for students `1` and `2`.

### Task 2: Routes, Instant Issuance, Billing, Campus & 4-Tab Staff Backend
**Files:**
- Modify: `semester/__init__.py`
- Modify: `semester/templates/components.html`
- Test: `tests/test_portal.py`

- [x] Add instant certificate endpoint `POST /requests/instant/<kind>`, specialized document data (`military`, `income`, `dorm_cert`) in `/requests/<id>/document`, and `POST /requests/slot` for window `А–116` booking.
- [x] Add `/campus`, `POST /campus/pay/<charge_id>`, `/campus/receipt/<charge_id>`, `POST /campus/guest-pass`, `POST /campus/guest-pass/<pass_id>/revoke`, `POST /campus/book-room`, `POST /campus/book-room/<booking_id>/cancel`, and `/navigator`.
- [x] Upgrade `/staff` (`tab` in `queue`, `schedule`, `students`, `notices`), `POST /staff/requests/<id>/resolve` (`approved` vs `returned`), `POST /staff/schedule/override`, `POST /staff/schedule/override/<id>/clear`, and `POST /staff/announcements/<id>/delete`.

### Task 3: Templates, Aligned `/staff` UI & Responsive CSS/JS
**Files:**
- Modify: `semester/templates/base.html`, `home.html`, `requests.html`, `request_new.html`, `request_detail.html`, `document.html`, `schedule.html`, `grades.html`, `staff.html`
- Create: `semester/templates/campus.html`, `semester/templates/receipt.html`, `semester/templates/navigator.html`
- Modify: `semester/static/portal.css`, `semester/static/portal.js`

- [x] Build clean Adwaita/Revolut surfaces for `/campus`, `/campus/receipt/<id>`, `/navigator`, upgraded `/requests` (1-click instant certificates + petitions + slot booking), and aligned 4-tab `/staff` workspace.
- [x] Update `portal.css` and `portal.js` (preset reply buttons, live navigator search filter, guest pass modal, zero inline styles, `360px`–`1440px` responsive rules).

### Task 4: Automated Security/UI Verification & Deliverables Refresh
**Files:**
- Modify: `tests/test_portal.py`, `README.md`, `docs/design.md`, `docs/ai-process.md`, `work/report.py`

- [x] Run unit tests covering instant certificates, dorm payment & receipt isolation, guest pass & booking lifecycle, navigator personalization, and staff room overrides + petition return/approval.
- [x] Run Playwright audit across `360px`, `1228px`, and `1440px` (Light & Dark) verifying zero overflow and zero CSP errors, restart `:8770`, and regenerate `outputs/*`.
