# Graph Report - vinta-os-1.6.3.2-main  (2026-10-11)

## Corpus Check
- 316 files · ~355,891 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 19 file(s) not represented in the graph (top: (none) 7, .spec 4, .example 2)

## Summary
- 3543 nodes · 9087 edges · 133 communities (115 shown, 18 thin omitted)
- Extraction: 95% EXTRACTED · 5% INFERRED · 0% AMBIGUOUS · INFERRED: 497 edges (avg confidence: 0.94)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- extensions.py
- cn
- verify_kit.py
- formatters.ts
- schemas/students.py
- schemas/billing.py
- PayoutDetailsCard.tsx
- schemas/attendance.py
- tenant_required
- SessionMenu.tsx
- Class
- routes/calendar.py
- User
- grossProfit.ts
- export_service.py
- react-i18next
- routes/notifications.py
- SessionDetail.tsx
- billing_service.py
- schemas/settings.py
- routes/settings.py
- scheduleDefs.ts
- TeacherDrawer.tsx
- CalendarPage.tsx
- scratch_pdf_language_check.py
- app/__init__.py
- DayPicker.tsx
- BillingConfig.tsx
- rate_limiter.py
- api.ts
- env.py
- routes/auth.py
- Academy
- billing.ts
- TestCheckOutFlow
- TestSessionCRUD
- Academy Root Entity
- constants.ts
- compilerOptions
- payout_schedule_service.py
- routes/students.py
- require_permission
- schemas/classes.py
- academy_data_service.py
- create_profile
- Luxury School OS Concept
- Session
- PayoutRecord
- schemas/teachers.py
- import_service.py
- SessionWindowModal.tsx
- index.ts
- routes/teachers.py
- launcher_os.py
- calendar.ts
- sessionTime.ts
- compilerOptions
- sys
- routes/attendance.py
- package.json
- student.ts
- academy_rules.py
- Teacher
- app/config.py
- BillingSummaryCard.tsx
- conftest.py
- uninstall.py
- auth_service.py
- school_export_service.py
- create_app
- launcher.py
- setup_boot.py
- token_blacklist.py
- permissions.py
- shortcuts.py
- test_cancel_session.py
- seed/run.py
- register_error_handlers
- PaymentPlan
- ClassesPage.tsx
- s07_money.py
- permissions.ts
- marshmallow
- payoutSchedule.ts
- billingRules.ts
- build_usb.py
- StudentBilling
- scratch_payout_chart_check.py
- themeStore.ts
- AgendaBoard.tsx
- Expense
- .oxlintrc.json
- ErrorBoundary
- SchedulingModal.tsx
- build_review_build.py
- pathlib
- Translation conventions — Vinta School OS
- Vinta School OS — Billing Guide
- SessionCheckInModal
- Graphify Knowledge Graph Rules
- StudentGuardians.tsx
- tsconfig.json
- routes/__init__.py
- Analytics & Reports Blueprint (/api/analytics)
- Settings Blueprint (/api/settings)
- Teacher Revenue Split Model
- schemas/__init__.py
- PaymentHistoryList.tsx
- selfhost_fonts.py
- StudentAttendanceCalendar.tsx
- teacherEmails.ts
- teacher.ts
- _date
- scratch_permissions_check.py
- StudentDrawer.tsx
- Vinta School OS App Icon
- Vite Tooling Asset
- tasks/__init__.py
- utils/__init__.py
- tests/__init__.py
- integration/__init__.py
- unit/__init__.py
- export_billing_records
- Avatar.tsx
- DayView.tsx
- toLocalISO
- voidedSessions.ts
- start.sh
- Vite React TypeScript Architecture
- vercel.json
- get_teacher_payments
- findConflicts

## God Nodes (most connected - your core abstractions)
1. `cn()` - 211 edges
2. `tenant_required()` - 130 edges
3. `require_permission()` - 102 edges
4. `react-i18next` - 94 edges
5. `react` - 93 edges
6. `lucide-react` - 80 edges
7. `Session` - 79 edges
8. `User` - 74 edges
9. `Class` - 67 edges
10. `Student` - 54 edges

## Surprising Connections (you probably didn't know these)
- ``revenue_entries` — one seat, one session (`app/models/billing.py:207-241`)` --references--> `record_checkin_billing_side_effects()`  [INFERRED]
  Docs/Billing-Guide.md → Backend/vinta-academy-backend/app/services/billing_service.py
- `5.3 The full-school archive` --references--> `build_school_archive()`  [INFERRED]
  Docs/Billing-Guide.md → Backend/vinta-academy-backend/app/services/school_export_service.py
- `Step 1 — a student is enrolled in a course group` --references--> `materialize_roster()`  [INFERRED]
  Docs/Billing-Guide.md → Backend/vinta-academy-backend/app/services/session_lifecycle_service.py
- `Step 3 — the class is started, and the register is created` --references--> `materialize_roster()`  [INFERRED]
  Docs/Billing-Guide.md → Backend/vinta-academy-backend/app/services/session_lifecycle_service.py
- `7. Where the numbers can go wrong` --references--> `ActivityLog`  [INFERRED]
  Docs/Billing-Guide.md → Backend/vinta-academy-backend/app/models/audit.py

## Import Cycles
- 2-file cycle: `Backend/vinta-academy-backend/app/services/billing_service.py -> Backend/vinta-academy-backend/app/services/import_service.py -> Backend/vinta-academy-backend/app/services/billing_service.py`
- 3-file cycle: `Backend/vinta-academy-backend/app/__init__.py -> Backend/vinta-academy-backend/app/routes/attendance.py -> Backend/vinta-academy-backend/app/utils/decorators.py -> Backend/vinta-academy-backend/app/__init__.py`
- 3-file cycle: `Backend/vinta-academy-backend/app/__init__.py -> Backend/vinta-academy-backend/app/routes/billing.py -> Backend/vinta-academy-backend/app/utils/decorators.py -> Backend/vinta-academy-backend/app/__init__.py`
- 3-file cycle: `Backend/vinta-academy-backend/app/__init__.py -> Backend/vinta-academy-backend/app/routes/settings.py -> Backend/vinta-academy-backend/app/services/auth_service.py -> Backend/vinta-academy-backend/app/__init__.py`
- 3-file cycle: `Backend/vinta-academy-backend/app/__init__.py -> Backend/vinta-academy-backend/app/routes/settings.py -> Backend/vinta-academy-backend/app/utils/decorators.py -> Backend/vinta-academy-backend/app/__init__.py`
- 3-file cycle: `Backend/vinta-academy-backend/app/__init__.py -> Backend/vinta-academy-backend/app/routes/teachers.py -> Backend/vinta-academy-backend/app/utils/decorators.py -> Backend/vinta-academy-backend/app/__init__.py`
- 3-file cycle: `Backend/vinta-academy-backend/app/__init__.py -> Backend/vinta-academy-backend/app/routes/calendar.py -> Backend/vinta-academy-backend/app/utils/decorators.py -> Backend/vinta-academy-backend/app/__init__.py`
- 3-file cycle: `Backend/vinta-academy-backend/app/__init__.py -> Backend/vinta-academy-backend/app/routes/classes.py -> Backend/vinta-academy-backend/app/utils/decorators.py -> Backend/vinta-academy-backend/app/__init__.py`
- 3-file cycle: `Backend/vinta-academy-backend/app/__init__.py -> Backend/vinta-academy-backend/app/routes/analytics.py -> Backend/vinta-academy-backend/app/utils/decorators.py -> Backend/vinta-academy-backend/app/__init__.py`
- 3-file cycle: `Backend/vinta-academy-backend/app/__init__.py -> Backend/vinta-academy-backend/app/routes/notifications.py -> Backend/vinta-academy-backend/app/utils/decorators.py -> Backend/vinta-academy-backend/app/__init__.py`
- 3-file cycle: `Backend/vinta-academy-backend/app/__init__.py -> Backend/vinta-academy-backend/app/routes/students.py -> Backend/vinta-academy-backend/app/utils/decorators.py -> Backend/vinta-academy-backend/app/__init__.py`
- 3-file cycle: `Backend/vinta-academy-backend/app/services/billing_service.py -> Backend/vinta-academy-backend/app/utils/formatters.py -> Backend/vinta-academy-backend/app/services/import_service.py -> Backend/vinta-academy-backend/app/services/billing_service.py`

## Hyperedges (group relationships)
- **Multi-Tenant Core Architecture & Domain Boundaries** — docs_documentation_tenant_isolation_model, docs_documentation_entity_academy, backend_api_architecture_overview, docs_documentation_billing_architecture [EXTRACTED 1.00]

## Communities (133 total, 18 thin omitted)

### Community 0 - "extensions.py"
Cohesion: 0.06
Nodes (51): Vinta School OS — Extension Initialization Centralized extension instances for…, Turn on foreign key enforcement for every SQLite connection as it opens.…, _sqlite_enable_foreign_keys(), Vinta School OS — Academy & Tenant Models Academy (tenant root),…, Vinta School OS — Attendance Model SessionStudent: tracks check-in/out per…, ActivityLog, Vinta School OS — Activity Log & Audit Trail Model Every significant action is…, Audit trail. Every significant action in the system is logged with user_id —… (+43 more)

### Community 1 - "cn"
Cohesion: 0.05
Nodes (81): lucide-react, react, PageContainer(), PageContainerProps, Badge, BadgeProps, SemanticVariant, sizeStyles (+73 more)

### Community 2 - "verify_kit.py"
Cohesion: 0.14
Nodes (20): Snap a time to the nearest 5-minute grid., Snap a time object to the nearest 5-minute grid., snap_time(), snap_time_obj(), Popen, shutil, socket, subprocess (+12 more)

### Community 3 - "formatters.ts"
Cohesion: 0.07
Nodes (34): recharts, AddPayoutModal(), AddPayoutModalProps, BASES, BASIS_LABEL_KEY, PinInput(), BillingPage(), BillingTab (+26 more)

### Community 4 - "schemas/students.py"
Cohesion: 0.11
Nodes (25): AddGuardianRequestSchema, CreateStudentRequestSchema, CreateStudentResponseSchema, EnrollmentSchema, EnrollResponseSchema, EnrollStudentRequestSchema, GuardianSchema, Schema (+17 more)

### Community 5 - "schemas/billing.py"
Cohesion: 0.05
Nodes (53): AgingBucketsResponseSchema, BillingStatsResponseSchema, CreatePayoutRequestSchema, CreatePlanRequestSchema, FinalizeSessionRequestSchema, FinalizeSessionResponseSchema, MarkPayoutPaidRequestSchema, PaymentPlanListResponseSchema (+45 more)

### Community 6 - "PayoutDetailsCard.tsx"
Cohesion: 0.06
Nodes (50): RFC-5987, maxWidthMap, Modal, ModalProps, BillingExportModal(), BillingExportModalProps, Format, FORMATS (+42 more)

### Community 7 - "schemas/attendance.py"
Cohesion: 0.10
Nodes (27): AddToSessionRequestSchema, AddToSessionResponseSchema, AutoCheckoutRequestSchema, AutoCheckoutResponseSchema, CheckInRequestSchema, CheckInResponseSchema, CheckOutRequestSchema, CheckOutResponseSchema (+19 more)

### Community 8 - "tenant_required"
Cohesion: 0.06
Nodes (77): check_overdue(), create_expense(), create_payout(), create_plan(), delete_expense(), expense_categories(), expense_summary(), export_records() (+69 more)

### Community 9 - "SessionMenu.tsx"
Cohesion: 0.04
Nodes (89): RosterEntry, SessionCheckInModalProps, STATUS_CONFIG, StudentSearchResult, ClassCardMenu(), EndClassModal(), FreeChip(), isRunning() (+81 more)

### Community 10 - "Class"
Cohesion: 0.06
Nodes (56): Class, A subject offering (e.g., 'Math — CM2'). Enrollment target for students., Enrollment, Guardian, Many-to-many: Student ↔ Class through Enrollment., A child enrolled in the academy., Student guardian / emergency contact. One student can have multiple guardians., Student (+48 more)

### Community 11 - "routes/calendar.py"
Cohesion: 0.07
Nodes (44): add_student_to_session(), cancel_session(), create_session(), _duration_label(), end_session(), get_day(), get_session_roster(), get_week() (+36 more)

### Community 12 - "User"
Cohesion: 0.06
Nodes (32): Verify a password against the stored hash., Set a new password hash (owner only)., Whether this user may do ``need`` in ``area``. A thin reading of…, Every person who logs into the system. Owner or Staff., Canonical form of an email address, for storage and for lookup. Login resolves…, Hash a 4-digit PIN using bcrypt., Verify a PIN against the stored hash., Hash a password using bcrypt. (+24 more)

### Community 13 - "grossProfit.ts"
Cohesion: 0.60
Nodes (4): currentAcademy(), save(), setGrossProfitEnabled(), Store

### Community 14 - "export_service.py"
Cohesion: 0.08
Nodes (40): _ascii_slug(), _cadence_phrase(), _ensure_font(), export_chart_data(), _export_meta(), export_teacher_payout(), _payout_period(), _payout_period_span() (+32 more)

### Community 15 - "react-i18next"
Cohesion: 0.04
Nodes (74): react-i18next, react-router-dom, zustand, App(), Providers(), ProvidersProps, TOAST_COLORS, TOAST_ICONS (+66 more)

### Community 16 - "routes/notifications.py"
Cohesion: 0.12
Nodes (26): Notification, In-app toast notification / alert., create_notification(), get_unread_count(), list_notifications(), mark_all_read(), mark_read(), jwt_required (+18 more)

### Community 17 - "SessionDetail.tsx"
Cohesion: 0.12
Nodes (21): PINInput, PINInputProps, PinStep(), PinStepProps, InfoChipProps, RosterStudent, SessionDetail, startTimeLabel() (+13 more)

### Community 18 - "billing_service.py"
Cohesion: 0.06
Nodes (56): Student purchase of a Class offer (credit-based or time-based). Table name is…, StudentSubscription, default_teacher_share_percentage(), The academy's default teacher share of gross, as a whole percent (0–100). The…, _collected_between(), create_multi_payment(), create_subscription(), create_subscription_for_payment() (+48 more)

### Community 19 - "schemas/settings.py"
Cohesion: 0.08
Nodes (36): PermissionGrantSchema, What a user may do — the resolved grant, not the stored column. Handed to the…, AcademyResponseSchema, AddStaffRequestSchema, AddStaffResponseSchema, AppearanceResponseSchema, AutomationsResponseSchema, BillingConfigResponseSchema (+28 more)

### Community 20 - "routes/settings.py"
Cohesion: 0.07
Nodes (54): _coerce_bool(), deactivate_staff(), delete_staff(), export_school(), get_academy(), get_activity_log(), get_appearance(), get_automations() (+46 more)

### Community 21 - "scheduleDefs.ts"
Cohesion: 0.15
Nodes (22): ConflictSession, createScheduleDef(), createTempRecord(), DAY_OPTIONS, deleteScheduleDef(), getDefsForClass(), getScheduleDef(), getSessionOrigin() (+14 more)

### Community 22 - "TeacherDrawer.tsx"
Cohesion: 0.11
Nodes (21): COMMISSION_SUFFIX_KEYS, COMMISSION_TYPE_KEYS, commissionBadgeLabel(), commissionRateLabel(), DAY_ANCHORS, DAYS, editInputCls, EMPTY_PAYOUT_DRAFT (+13 more)

### Community 23 - "CalendarPage.tsx"
Cohesion: 0.16
Nodes (17): CalendarPage(), REASON_KEYS, STATUS_KEYS, errMsg(), GroupOption, RoomOption, SessionWindowModal(), TeacherOption (+9 more)

### Community 24 - "scratch_pdf_language_check.py"
Cohesion: 0.09
Nodes (19): Backend string catalogue. One entry per language, one entry per key, English…, _accepted_tags(), Vinta School OS — backend translations. Why the server translates anything at…, The language to write in, given a request's ``Accept-Language``. Accepts the…, Looks up backend strings for one language. Callable rather than a ``get``…, A translator for `language`, which may be a raw ``Accept-Language``., Language tags from an ``Accept-Language`` header, most wanted first. A browser…, resolve_language() (+11 more)

### Community 25 - "app/__init__.py"
Cohesion: 0.11
Nodes (21): Vinta School OS — Application Factory Creates and configures the Flask…, export_data(), get_dashboard(), jwt_required, route, Vinta School OS — Analytics Blueprint /api/analytics — Dashboard stats, Revenue…, Export data as CSV. Supported datasets: students, billing, teacher_hours,…, Dashboard overview stats. Returns: total students, total teachers, total… (+13 more)

### Community 26 - "DayPicker.tsx"
Cohesion: 0.21
Nodes (13): NotificationBell(), relativeTime(), styleFor(), TYPE_STYLE, DayPicker(), DayPickerProps, sizeStyles, todayISO() (+5 more)

### Community 27 - "BillingConfig.tsx"
Cohesion: 0.12
Nodes (23): AppearanceProps, BillingConfig(), BillingConfigProps, BillingPreset, BUILT_IN_PRESET_KEYS, CADENCE_KEY, CURRENCY_OPTIONS, DEFAULT_PRESETS (+15 more)

### Community 28 - "rate_limiter.py"
Cohesion: 0.50
Nodes (3): Rate limiting configuration for authentication endpoints., flask_limiter, flask_limiter_util

### Community 29 - "api.ts"
Cohesion: 0.07
Nodes (35): LineItem, MultiPayModal(), PAYMENT_METHODS, PinInput(), BILLING_MODEL_STYLE, STATUS_STYLE, SubscriptionsPanel(), SubscriptionsPanelProps (+27 more)

### Community 30 - "env.py"
Cohesion: 0.13
Nodes (13): alembic, get_engine(), get_engine_url(), get_metadata(), Run migrations in 'offline' mode. This configures the context with just a URL…, Run migrations in 'online' mode. In this scenario we need to create an Engine…, run_migrations_offline(), run_migrations_online() (+5 more)

### Community 31 - "routes/auth.py"
Cohesion: 0.10
Nodes (34): Vinta School OS — Auth Blueprint /api/auth — Login, Profile Selection, PIN…, ChangePinRequestSchema, CreateOwnerRequestSchema, CreateOwnerResponseSchema, CreateProfileRequestSchema, LoginRequestSchema, MeResponseSchema, Meta (+26 more)

### Community 32 - "Academy"
Cohesion: 0.04
Nodes (36): Academy, AcademySettings, Academy SaaS subscription tier., Top-level tenant entity. One academy = one private school/academy., Per-academy configuration singleton., Subscription, check_overdue_billings(), Check for billings that are past due_date and mark them as overdue. Returns… (+28 more)

### Community 33 - "billing.ts"
Cohesion: 0.05
Nodes (39): AgingBucket, BillingRecord, BillingRecordDirection, BillingRecordKind, BillingRecordsResponse, BillingRecordsTotals, BillingRingData, BillingState (+31 more)

### Community 34 - "TestCheckOutFlow"
Cohesion: 0.10
Nodes (14): integration, Test session roster operations., New session should have empty roster., Should be able to add a student to a session roster., Adding the same student twice should return existing record., Test auto-checkout trigger., Auto-checkout should check out all present students., Test student check-out from session. (+6 more)

### Community 35 - "TestSessionCRUD"
Cohesion: 0.07
Nodes (17): integration, Should update session date via PATCH., Moved session times should snap to 5-minute grid., Should cancel a session via DELETE., Test recurring schedule → session generation., Test session create/read/update/delete via API., Creating a schedule should auto-generate sessions for 12 weeks., Should create a new session with valid data. (+9 more)

### Community 36 - "Academy Root Entity"
Cohesion: 0.11
Nodes (18): Attendance Blueprint (/api/attendance), Billing & Subscriptions Blueprint (/api/billing), Calendar & Sessions Blueprint (/api/sessions), Classes & Groups Blueprint (/api/classes), Students Blueprint (/api/students), Teachers Blueprint (/api/teachers), Session Attendance & Check-in/out Flow, Student Tuition & Credit/Time Billing Architecture (+10 more)

### Community 37 - "constants.ts"
Cohesion: 0.07
Nodes (26): ACADEMY_ID_KEY, ACTIVITY_TYPES, API_BASE_URL, AvatarPreset, BREAKPOINTS, CHART_COLORS, DEFAULT_SESSION_DURATION, ENTITY_FILTER_PAGES (+18 more)

### Community 38 - "compilerOptions"
Cohesion: 0.07
Nodes (26): compilerOptions, allowArbitraryExtensions, allowImportingTsExtensions, baseUrl, erasableSyntaxOnly, forceConsistentCasingInFileNames, ignoreDeprecations, isolatedModules (+18 more)

### Community 39 - "payout_schedule_service.py"
Cohesion: 0.05
Nodes (58): PayoutSchedule, When a teacher is paid — a cadence, not an event. Why this table exists at all,…, Session length in hours from start/end times (min 1h fallback)., _session_duration_hours(), _datetime(), _clamp_day(), delete_schedule(), _distinct_students_taught() (+50 more)

### Community 40 - "routes/students.py"
Cohesion: 0.11
Nodes (29): add_guardian(), bulk_enroll_students(), create_student(), delete_student(), enroll_student(), get_stats(), get_student(), list_guardians() (+21 more)

### Community 41 - "require_permission"
Cohesion: 0.08
Nodes (51): _apply_group_fields(), create_class(), create_classroom(), create_schedule(), create_subject(), delete_class(), delete_classroom(), delete_schedule() (+43 more)

### Community 42 - "schemas/classes.py"
Cohesion: 0.12
Nodes (24): ClassListResponseSchema, ClassListSchema, ClassroomListResponseSchema, ClassroomSchema, CreateClassRequestSchema, CreateClassResponseSchema, CreateClassroomRequestSchema, CreateScheduleRequestSchema (+16 more)

### Community 43 - "academy_data_service.py"
Cohesion: 0.18
Nodes (16): _academy_owned_tables(), _collect(), _delete(), _delete_where(), _foreign_keys(), _primary_key(), purge_academy_data(), Vinta School OS — Academy Data Purge One ordered, foreign-key-safe way to… (+8 more)

### Community 44 - "create_profile"
Cohesion: 0.13
Nodes (30): arguments, change_pin(), create_owner(), create_profile(), get_current_user(), get_profiles(), login(), logout() (+22 more)

### Community 45 - "Luxury School OS Concept"
Cohesion: 0.12
Nodes (17): Flask REST API Architecture, Auth Blueprint (/api/auth), Two-Stage Auth & Profile PIN Verification Flow, Docker Compose Local Environment, Flask & SQLAlchemy Dependencies, PIN-Attributed Activity Log & Audit Trail, Algerian Private Academy Target Market, Glassmorphic Design Tokens (--gold / --emerald) (+9 more)

### Community 46 - "Session"
Cohesion: 0.04
Nodes (85): Many-to-many: Session ↔ Student. Tracks attendance (is_present, check-in/out…, SessionStudent, A concrete class session on a specific date. Generated from Schedule or created…, Session, absence_consumes_credit(), Toggle 1 — does a missed session still spend a credit? True (default): an…, add_student_to_session(), auto_checkout_session() (+77 more)

### Community 47 - "PayoutRecord"
Cohesion: 0.07
Nodes (32): PayoutRecord, Money owed to a teacher — either derived from a session, or recorded by hand.…, _compute_teacher_cut(), create_manual_payout(), finalize_session(), list_billing_records(), list_payouts(), mark_payout_paid() (+24 more)

### Community 48 - "schemas/teachers.py"
Cohesion: 0.14
Nodes (19): CreateTeacherRequestSchema, CreateTeacherResponseSchema, PayrollSummarySchema, Schema, Teacher schemas — CRUD, Contracts, Payroll., POST /api/teachers response., PUT /api/teachers/<id>, Single teacher in list. (+11 more)

### Community 49 - "import_service.py"
Cohesion: 0.09
Nodes (41): create_expense(), Record a school expense. Raises ValueError on a bad field., _amount(), _build_context(), candidates_for(), _decode(), detect_dataset(), _digits() (+33 more)

### Community 50 - "SessionWindowModal.tsx"
Cohesion: 0.06
Nodes (46): react-dom, Drawer, DrawerProps, Select, SelectAction, SelectOption, SelectProps, Column() (+38 more)

### Community 51 - "index.ts"
Cohesion: 0.05
Nodes (38): DEFAULT_LANGUAGE, DIRECTION, initialLanguage, LANGUAGE_LABELS, Namespace, NAMESPACES, resources, SUPPORTED_LANGUAGES (+30 more)

### Community 52 - "routes/teachers.py"
Cohesion: 0.09
Nodes (32): Extensible palette entity for calendar subject colors., Subject, Junction table for teacher-subject many-to-many relationship., TeacherSubject, _clean_email(), _clean_status(), create_teacher(), delete_teacher() (+24 more)

### Community 53 - "launcher_os.py"
Cohesion: 0.11
Nodes (31): threading, app_dir(), bundle_dir(), choose_port(), configure_environment(), default_data_dir(), fatal(), harden_console() (+23 more)

### Community 54 - "calendar.ts"
Cohesion: 0.15
Nodes (14): hexToRgba(), SessionBlock(), SessionBlockProps, SubjectPaletteProps, WeekViewProps, CalendarSession, CalendarState, CalendarViewMode (+6 more)

### Community 55 - "sessionTime.ts"
Cohesion: 0.23
Nodes (9): layoutDay(), SlotLayout, Span, spanOf(), DAY_NAMES, enrichSession(), timeLabel(), timeRangeLabel() (+1 more)

### Community 56 - "compilerOptions"
Cohesion: 0.12
Nodes (16): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, noEmit, noFallthroughCasesInSwitch (+8 more)

### Community 57 - "sys"
Cohesion: 0.08
Nodes (30): main(), Schema step — expenses.quantity. WHY §11 of the billing brief asks an owner to…, Resolve the SQLite file the app actually opens, from DATABASE_URL., resolve_db_path(), main(), Additive migration — billing relations, session lifecycle, billing toggles.…, Resolve the SQLite file the app actually opens, from DATABASE_URL., resolve_db_path() (+22 more)

### Community 58 - "routes/attendance.py"
Cohesion: 0.11
Nodes (28): add_to_session(), auto_checkout(), check_in(), check_out(), complete_session(), get_roster(), guest_check_in(), jwt_required (+20 more)

### Community 59 - "package.json"
Cohesion: 0.04
Nodes (44): axios, clsx, oxlint, ref_path, tailwind-merge, tailwindcss, @tailwindcss/vite, @types/node (+36 more)

### Community 60 - "student.ts"
Cohesion: 0.09
Nodes (26): i18next, MultiPayModalProps, AddStudentModal(), BillingSummaryCardProps, StudentIdentityProps, UseStudentProfileResult, StudentDrawerProps, activePillClass() (+18 more)

### Community 61 - "academy_rules.py"
Cohesion: 0.17
Nodes (15): count_gap_sessions(), early_payment_on_extra_sessions(), free_session_auto_present(), Vinta School OS — Academy Rules Per-academy policy, read at the moment a…, The academy's settings row, or None if it has never been created., Read one boolean rule, falling back to its documented default., Toggle 2 — are sessions missed during a payment gap charged later? True:…, Toggle 5 — give credits back when a class is cancelled after charging? False… (+7 more)

### Community 62 - "Teacher"
Cohesion: 0.05
Nodes (48): apscheduler_schedulers_background, Monthly payroll record for each teacher., An instructor employed by the academy., Records when a teacher's hours are logged (per session)., Teacher, TeacherHoursLog, TeacherPayroll, export_teacher_hours() (+40 more)

### Community 63 - "app/config.py"
Cohesion: 0.19
Nodes (12): BaseConfig, DevelopmentConfig, ProductionConfig, Vinta School OS — Configuration Environments Dev, Test, and Production…, Shared configuration across all environments., Development environment configuration., Test environment configuration., Production environment configuration. (+4 more)

### Community 64 - "BillingSummaryCard.tsx"
Cohesion: 0.22
Nodes (18): BillingCalendarCard(), BillingCalendarCardProps, CYCLE_STATUS_KEYS, statusDot(), activeLocale(), BillingSummaryCard(), formatDateRange(), formatDisplayDate() (+10 more)

### Community 65 - "conftest.py"
Cohesion: 0.10
Nodes (26): Recurring weekly slot defining when a class meets., Schedule, generate_sessions_from_schedule(), Generate concrete Session instances from a recurring Schedule entry. Creates…, academy(), app(), auth_headers_owner(), auth_headers_staff() (+18 more)

### Community 66 - "uninstall.py"
Cohesion: 0.16
Nodes (24): tempfile, ask(), data_dir(), fs(), hand_over_to_temp_copy(), install_dir(), is_inside(), main() (+16 more)

### Community 67 - "auth_service.py"
Cohesion: 0.10
Nodes (23): add_staff(), Add a new staff profile (requires the staff permission + the caller's PIN).…, authenticate_credentials(), authenticate_profile(), change_password(), change_pin(), clean_email(), clean_password() (+15 more)

### Community 68 - "school_export_service.py"
Cohesion: 0.14
Nodes (19): collect_academy_keys(), The primary-key tuples of every row the academy owns, per table. The same…, build_school_archive(), _cell(), _database_snapshot(), _iter_rows(), _jsonable(), Vinta School OS — School Export ("everything" archive) One download that… (+11 more)

### Community 69 - "create_app"
Cohesion: 0.12
Nodes (15): create_app(), check_if_token_revoked(), Register all API blueprints., Application factory pattern., Register shell context objects., _register_blueprints(), _register_shell_context(), make_shell_context() (+7 more)

### Community 70 - "launcher.py"
Cohesion: 0.16
Nodes (21): bundle_dir(), choose_port(), configure_environment(), install_dir(), load_or_create_secrets(), looks_like_our_app(), main(), port_is_free() (+13 more)

### Community 71 - "setup_boot.py"
Cohesion: 0.18
Nodes (23): copy_application(), exe_dir(), fail(), find_payload(), fs(), initialise_database(), is_locked(), main() (+15 more)

### Community 72 - "token_blacklist.py"
Cohesion: 0.33
Nodes (5): blacklist_token(), cleanup_expired(), Simple in-memory token blacklist for JWT revocation. For production, replace…, Add a token JTI to the blacklist., Remove expired entries from the blacklist.

### Community 73 - "permissions.py"
Cohesion: 0.18
Nodes (22): Any, allowed(), allowed_any(), catalogue(), _clean_actions(), _clean_levels(), describe(), effective() (+14 more)

### Community 74 - "shortcuts.py"
Cohesion: 0.13
Nodes (22): c_void_p, ctypes, create_shortcuts(), Put Vinta OS on the Desktop and in the Start Menu. Returns (made, failed)., _check(), create_shortcut(), data_dir(), desktop_dir() (+14 more)

### Community 75 - "test_cancel_session.py"
Cohesion: 0.16
Nodes (21): cancel_session(), Cancel a session, recording *why*. The reason is not decoration:…, Vinta School OS — cancelling a session. ``cancel_session`` is reached from…, CANCEL_REASONS is a plain Python tuple; the column is a native enum that knows…, An unrecognised reason is a label problem, not a reason to lose the cancel., A bare DELETE still cancels; it just does not claim to know why., Tenant scoping — the lookup is by id AND academy., A class that has not run can be called off; a class that is running can be… (+13 more)

### Community 76 - "seed/run.py"
Cohesion: 0.16
Nodes (18): _assert_deletable(), _assert_target(), _build_parser(), _force_utf8_stdout(), _local_db_path(), main(), _module_index(), _print_summary() (+10 more)

### Community 78 - "PaymentPlan"
Cohesion: 0.05
Nodes (40): PaymentPlan, Reusable billing plans that can be assigned to students., create_payment_plan(), get_aging_buckets(), list_payment_plans(), list_student_billings(), List all payment plans for an academy., Create a new payment plan. (+32 more)

### Community 79 - "ClassesPage.tsx"
Cohesion: 0.06
Nodes (56): PinConfirmDialog(), PinConfirmDialogProps, ClassCardMenuProps, BillingBadge, BillingReading, ClassDetail(), ClassDetailProps, COLOR_PRESETS (+48 more)

### Community 80 - "s07_money.py"
Cohesion: 0.04
Nodes (84): Classroom, A physical room in the academy., seed.config — every constant the seeder uses. Nothing here imports from…, bulk_insert(), _fill_primary_key(), hex_color(), log(), month_iter() (+76 more)

### Community 81 - "permissions.ts"
Cohesion: 0.05
Nodes (59): AppShell(), AddStaffModal(), AddStaffModalProps, inputCls, EditStaffModal(), EditStaffModalProps, inputCls, PermissionEditor() (+51 more)

### Community 82 - "marshmallow"
Cohesion: 0.29
Nodes (7): DashboardResponseSchema, Schema, Analytics schemas — Dashboard stats, Revenue chart, CSV export., GET /api/analytics/revenue-chart response., GET /api/analytics/dashboard response., RevenueChartResponseSchema, marshmallow

### Community 83 - "payoutSchedule.ts"
Cohesion: 0.15
Nodes (20): 4.4 Nothing runs on a timer — and what that means for you, PayoutDetails, asCadence(), asDay(), asIsoDate(), DEFAULT_DAY_OF_MONTH, DEFAULT_DAY_OF_WEEK, DueTeacher (+12 more)

### Community 84 - "billingRules.ts"
Cohesion: 0.13
Nodes (18): ClassBillingStat(), fetchBilling(), BILLING_RULE_DEFAULTS, BILLING_RULE_FIELDS, BillingRuleField, cache, DebtRow, debtUid() (+10 more)

### Community 85 - "build_usb.py"
Cohesion: 0.27
Nodes (19): log(), main(), Path, Build the Vinta OS USB kit. Everything that has to be true is made true here,…, Prove the frozen application starts and answers before it is shipped. A frozen…, Run a program directly (no shell), so spaces in paths stay intact., Run a shell command line. Needed for npm/npx, which on Windows are .cmd shims…, report() (+11 more)

### Community 86 - "StudentBilling"
Cohesion: 0.09
Nodes (18): PaymentLog, Vinta School OS — Billing Models PaymentPlan, StudentBilling, PaymentLog…, Immutable revenue fact per conducted session allocation (DZD integers)., One record per billing cycle per student. Core billing entity., Individual payment transactions against a billing record., RevenueEntry, StudentBilling, get_revenue() (+10 more)

### Community 87 - "scratch_payout_chart_check.py"
Cohesion: 0.14
Nodes (7): Scratch smoke test for the new billing endpoints. Delete when done. Exercises,…, Owner-only enforcement, proven against the running dev server. Delete when…, Teacher cost in the monthly chart — before and after. Delete when done. The…, Live RBAC smoke test — drives the running dev server on :5000 the way the…, json, urllib_error, urllib_request

### Community 88 - "themeStore.ts"
Cohesion: 0.16
Nodes (19): applyDocumentLanguage(), Language, readStoredLanguage(), FONT_SIZE_KEY, LANGUAGE_KEY, THEME_KEY, applyFontSize(), applyLanguage() (+11 more)

### Community 89 - "AgendaBoard.tsx"
Cohesion: 0.20
Nodes (19): decimalToTime(), snapHour(), toCalendarSession(), WeekView(), xToDayIndex(), yToTime(), AgendaBoard(), hexToRgba() (+11 more)

### Community 90 - "Expense"
Cohesion: 0.13
Nodes (16): Expense, A school operating expense — money that left the academy. Deliberately its own…, delete_expense(), get_expense(), list_expenses(), _parse_amount(), _parse_quantity(), A positive integer DZD amount, or a ValueError. Expenses are recorded as… (+8 more)

### Community 91 - ".oxlintrc.json"
Cohesion: 0.33
Nodes (5): plugins, rules, react/only-export-components, react/rules-of-hooks, $schema

### Community 93 - "SchedulingModal.tsx"
Cohesion: 0.15
Nodes (16): CONFLICT_KIND_KEYS, conflictKinds(), errMsg(), GroupOption, inputCls, Mode, primaryBtnCls, REASON_KEYS (+8 more)

### Community 94 - "build_review_build.py"
Cohesion: 0.33
Nodes (14): assemble(), build_frontend(), bundle_fonts(), freeze(), log(), main(), Path, Build the Vinta School OS offline review build. Produces a self-contained… (+6 more)

### Community 95 - "pathlib"
Cohesion: 0.19
Nodes (13): argparse, FreeTypeFont, Image, ImageFont, pathlib, pil, build_master(), gradient() (+5 more)

### Community 96 - "Translation conventions — Vinta School OS"
Cohesion: 0.14
Nodes (13): auth(), Dates, numbers, currency, Do not translate, Finishing, Interpolation and plurals, Key naming, Languages, Namespaces (+5 more)

### Community 97 - "Vinta School OS — Billing Guide"
Cohesion: 0.14
Nodes (13): format_dzd(), Format amount in Algerian Dinars with comma separators., 2.1 Money is integer DZD — no exceptions, 2.2 The money-model tables, 2.3 The supporting tables that define the prices, 2. The money tables, field by field, `expenses` — money out, no student (`app/models/billing.py:450-523`), `payout_records` — money owed to a teacher (`app/models/billing.py:244-335`) (+5 more)

### Community 98 - "SessionCheckInModal"
Cohesion: 0.32
Nodes (13): SessionCheckInModal(), createSwapLink(), getLinkByOriginal(), getLinkBySwap(), getLinksForStudent(), listSwapLinks(), loadAll(), removeLinkBySwap() (+5 more)

### Community 100 - "StudentGuardians.tsx"
Cohesion: 0.21
Nodes (11): EmptyLine(), InlineSpinner(), ProfileCard(), ProfileCardProps, StudentClasses(), StudentClassesProps, GuardianRow, StudentGuardians() (+3 more)

### Community 107 - "PaymentHistoryList.tsx"
Cohesion: 0.23
Nodes (12): DASH, humaniseStatus(), METHOD_LABEL_KEYS, METHOD_LABELS, methodLabel(), parseTimestamp(), PaymentHistoryList(), purchaseShape() (+4 more)

### Community 108 - "selfhost_fonts.py"
Cohesion: 0.36
Nodes (8): build_fonts(), fetch(), main(), patch_html(), Path, Bundle the frontend's webfonts into the app so it renders identically offline.…, Point the built index.html at the bundled fonts and tighten the CSP., slug()

### Community 109 - "StudentAttendanceCalendar.tsx"
Cohesion: 0.24
Nodes (11): dominantState(), formatTime(), monthCells(), STATE_PRIORITY, STATE_STYLES, StateStyle, StudentAttendanceCalendar(), StudentAttendanceCalendarProps (+3 more)

### Community 110 - "teacherEmails.ts"
Cohesion: 0.33
Nodes (9): RFC-5322, currentAcademy(), getTeacherEmail(), isValidEmail(), listTeacherEmails(), loadAll(), saveAll(), setTeacherEmail() (+1 more)

### Community 111 - "teacher.ts"
Cohesion: 0.17
Nodes (12): PayoutChoice, PayoutSchedule, BillingConfigResponse, COMMISSION_TYPE_LABELS, CommissionType, CreateTeacherRequest, TeacherHoursLog, TeacherPayoutSummary (+4 more)

### Community 112 - "_date"
Cohesion: 0.08
Nodes (27): _date(), get_class_sessions(), get_day_sessions(), get_week_sessions(), Serialize a session to a dict for API response. The lifecycle fields are part…, Get all sessions for a given week., Get all sessions for a specific day., Get one group's sessions, soonest first. A group's page needs its own sessions… (+19 more)

### Community 113 - "scratch_permissions_check.py"
Cohesion: 0.15
Nodes (11): RBAC enforcement, proven end to end through the real app. Delete when done.…, The source of a `const NAME = { ... }` or `[ ... ]` literal., _ts_block(), io, re, check_file(), flatten(), load() (+3 more)

### Community 114 - "StudentDrawer.tsx"
Cohesion: 0.24
Nodes (9): PaymentHistoryListProps, useStudentBilling(), UseStudentBillingResult, useStudentProfile(), ENROLLMENT_LABEL_KEYS, enrollmentLabel(), Field(), StudentDrawer() (+1 more)

### Community 122 - "export_billing_records"
Cohesion: 0.22
Nodes (10): billing_records_csv(), export_billing_records(), One billing record as export cells, matching BILLING_RECORD_HEADERS. The row…, The billing-records export as CSV text, with footer totals. Written in English…, The billing-records export, ready to hand to a response. Returns ``(payload,…, _record_row(), 5.1 Billing records — CSV and PDF, 5.3 The full-school archive (+2 more)

### Community 123 - "Avatar.tsx"
Cohesion: 0.33
Nodes (8): Avatar, AvatarProps, getGradientForName(), getInitials(), gradientPairs, hashCode(), sizeConfig, squircleRadius()

### Community 124 - "DayView.tsx"
Cohesion: 0.44
Nodes (8): DayView(), DayViewProps, decimalToTime(), snapHour(), toCalendarSession(), yToTime(), SNAP_MINUTES, timeToDecimal()

### Community 125 - "toLocalISO"
Cohesion: 0.33
Nodes (7): calendarRequest(), DashboardPage(), load(), loadStats(), isToday(), enrichSessions(), toLocalISO()

### Community 126 - "voidedSessions.ts"
Cohesion: 0.39
Nodes (8): getVoidRestore(), getVoidRestoredCredits(), isSessionVoided(), listVoidRestores(), loadAll(), recordVoidRestore(), saveAll(), VoidRestore

### Community 127 - "start.sh"
Cohesion: 0.50
Nodes (3): FLASK_APP, FLASK_ENV, start.sh script

### Community 128 - "Vite React TypeScript Architecture"
Cohesion: 0.67
Nodes (3): Vite React TypeScript Architecture, SPA HTML Entry Point, SVG Icon Sprite System

### Community 131 - "get_teacher_payments"
Cohesion: 0.29
Nodes (8): _class_ids_for_teacher(), count_students_for_teacher(), _distinct_students_for_classes(), get_teacher_payments(), Per-teacher payout totals, each with a breakdown by group. A teacher's revenue…, Every class (group) assigned to a teacher., Distinct active students enrolled in any of these classes., Active students across all of a teacher's groups, counted once each. Shared by…

### Community 132 - "findConflicts"
Cohesion: 0.67
Nodes (4): CompensatoryModal(), conflictLabels(), EditSessionModal(), findConflicts()

## Knowledge Gaps
- **485 isolated node(s):** `Meta`, `start.sh script`, `FLASK_APP`, `FLASK_ENV`, `$schema` (+480 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 1574 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **18 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `4.4 Nothing runs on a timer — and what that means for you` connect `payoutSchedule.ts` to `payout_schedule_service.py`, `Teacher`, `PayoutRecord`?**
  _High betweenness centrality (0.432) - this node is a cross-community bridge._
- **Why does `mark_payout_paid()` connect `PayoutRecord` to `tenant_required`, `billing_service.py`, `payoutSchedule.ts`, `Teacher`?**
  _High betweenness centrality (0.390) - this node is a cross-community bridge._
- **Why does `fetchAcademyPayoutSchedule()` connect `payoutSchedule.ts` to `BillingConfig.tsx`?**
  _High betweenness centrality (0.150) - this node is a cross-community bridge._
- **Are the 3 inferred relationships involving `tenant_required()` (e.g. with `Academy` and `User`) actually correct?**
  _`tenant_required()` has 3 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Meta`, `start.sh script`, `FLASK_APP` to the rest of the system?**
  _485 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `extensions.py` be split into smaller, more focused modules?**
  _Cohesion score 0.060764587525150904 - nodes in this community are weakly interconnected._
- **Should `cn` be split into smaller, more focused modules?**
  _Cohesion score 0.05164092664092664 - nodes in this community are weakly interconnected._