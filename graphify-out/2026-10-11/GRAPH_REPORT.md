# Graph Report - vinta-os-1.6.3.2-main  (2026-10-09)

## Corpus Check
- 303 files · ~317,961 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 15 file(s) not represented in the graph (top: (none) 7, .example 2, .ini 2)

## Summary
- 3220 nodes · 8247 edges · 131 communities (114 shown, 17 thin omitted)
- Extraction: 95% EXTRACTED · 5% INFERRED · 0% AMBIGUOUS · INFERRED: 403 edges (avg confidence: 0.94)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- extensions.py
- cn
- scheduling_service.py
- react
- schemas/students.py
- schemas/billing.py
- billing.ts
- schemas/attendance.py
- tenant_required
- ClassCardMenu.tsx
- Student
- jwt_required
- User
- SessionMenu.tsx
- SessionStudent
- react-i18next
- Notification
- SessionDetail.tsx
- billing_service.py
- schemas/settings.py
- routes/settings.py
- SchedulingModal.tsx
- uiStore.ts
- DashboardPage.tsx
- scratch_pdf_language_check.py
- export_service.py
- DayPicker.tsx
- BillingConfig.tsx
- rate_limiter.py
- api.ts
- env.py
- routes/auth.py
- TestAuthentication
- ActivityLog.tsx
- TestCheckInFlow
- TestSessionCRUD
- Academy Root Entity
- constants.ts
- compilerOptions
- formatters.py
- routes/students.py
- Class
- schemas/classes.py
- academy_data_service.py
- create_profile
- Luxury School OS Concept
- test_session_start_and_close.py
- GlobalSearch.tsx
- schemas/teachers.py
- import_service.py
- ClassQuickCreate.tsx
- index.ts
- test_cron_jobs.py
- TestTenantIsolation
- Session
- TimePicker.tsx
- compilerOptions
- sys
- record_checkin_billing_side_effects
- package.json
- routes/calendar.py
- academy_rules.py
- Session
- app/config.py
- formatters.ts
- class.ts
- add_staff
- _session_user
- school_export_service.py
- create_app
- launcher.py
- App.tsx
- token_blacklist.py
- permissions.py
- Guardian
- test_cancel_session.py
- seed/run.py
- register_error_handlers
- overdue_bucket
- ClassesPage.tsx
- s01_academy.py
- SettingsPage.tsx
- marshmallow
- _sqlite_enable_foreign_keys
- ClassDetail.tsx
- days_overdue
- TestBillingStatusDerivation
- scratch_payout_chart_check.py
- themeStore.ts
- .hash_password
- helpers.py
- .oxlintrc.json
- ErrorBoundary
- TestHourlyPayroll
- build_review_build.py
- ClassGrid.tsx
- Translation conventions — Vinta School OS
- s06_sessions.py
- schemas/notifications.py
- Graphify Knowledge Graph Rules
- _session_duration_hours
- tsconfig.json
- routes/__init__.py
- Analytics & Reports Blueprint (/api/analytics)
- Settings Blueprint (/api/settings)
- Teacher Revenue Split Model
- schemas/__init__.py
- DataImport.tsx
- selfhost_fonts.py
- run
- teacherEmails.ts
- start_session
- Vinta seeder
- scratch_permissions_check.py
- scratch_i18n_verify.py
- Vinta School OS App Icon
- Vite Tooling Asset
- tasks/__init__.py
- utils/__init__.py
- tests/__init__.py
- integration/__init__.py
- unit/__init__.py
- Classroom
- list_sessions
- ImportDetectionError
- update_session
- MultiPaymentError
- start.sh
- Vite React TypeScript Architecture
- vercel.json

## God Nodes (most connected - your core abstractions)
1. `cn()` - 209 edges
2. `tenant_required()` - 127 edges
3. `require_permission()` - 102 edges
4. `react-i18next` - 93 edges
5. `react` - 92 edges
6. `lucide-react` - 79 edges
7. `Session` - 75 edges
8. `User` - 74 edges
9. `Class` - 65 edges
10. `Student` - 54 edges

## Surprising Connections (you probably didn't know these)
- `ctx keys` --references--> `today()`  [INFERRED]
  Backend/vinta-academy-backend/seed/README.md → Backend/vinta-academy-backend/app/utils/formatters.py
- `Namespaces` --references--> `auth()`  [INFERRED]
  vinta-school-os/src/i18n/CONVENTIONS.md → Backend/vinta-academy-backend/scratch_import_http_check.py
- `Login Screen Hero Artwork` --conceptually_related_to--> `Glassmorphic Design Tokens (--gold / --emerald)`  [INFERRED]
  vinta-school-os/src/assets/hero.png → Docs/Notes.md
- `main()` --calls--> `create_app()`  [INFERRED]
  packaging/launcher.py → Backend/vinta-academy-backend/app/__init__.py
- `Helpers` --references--> `StudentSubscription`  [INFERRED]
  Backend/vinta-academy-backend/seed/README.md → Backend/vinta-academy-backend/app/models/billing.py

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

## Communities (131 total, 17 thin omitted)

### Community 0 - "extensions.py"
Cohesion: 0.05
Nodes (79): Vinta School OS — Extension Initialization Centralized extension instances for…, Vinta School OS — Application Factory Creates and configures the Flask…, Academy, AcademySettings, Vinta School OS — Academy & Tenant Models Academy (tenant root),…, Academy SaaS subscription tier., Top-level tenant entity. One academy = one private school/academy., Per-academy configuration singleton. (+71 more)

### Community 1 - "cn"
Cohesion: 0.05
Nodes (85): recharts, BillingPage, Badge, BadgeProps, SemanticVariant, sizeStyles, variantAliases, variantStyles (+77 more)

### Community 2 - "scheduling_service.py"
Cohesion: 0.16
Nodes (18): create_session(), get_day_sessions(), get_week_sessions(), _parse_time(), Vinta School OS — Scheduling Service Recurring slot generation, drag-to-…, Update session date/times (drag-to-move or edge-resize). Scheduled sessions are…, Snap a time to the nearest 5-minute grid., Snap a time object to the nearest 5-minute grid. (+10 more)

### Community 3 - "react"
Cohesion: 0.05
Nodes (47): lucide-react, react, react-dom, PageContainer(), PageContainerProps, DrawerProps, EmptyStateProps, Props (+39 more)

### Community 4 - "schemas/students.py"
Cohesion: 0.11
Nodes (25): AddGuardianRequestSchema, CreateStudentRequestSchema, CreateStudentResponseSchema, EnrollmentSchema, EnrollResponseSchema, EnrollStudentRequestSchema, GuardianSchema, Schema (+17 more)

### Community 5 - "schemas/billing.py"
Cohesion: 0.05
Nodes (53): AgingBucketsResponseSchema, BillingStatsResponseSchema, CreatePayoutRequestSchema, CreatePlanRequestSchema, FinalizeSessionRequestSchema, FinalizeSessionResponseSchema, MarkPayoutPaidRequestSchema, PaymentPlanListResponseSchema (+45 more)

### Community 6 - "billing.ts"
Cohesion: 0.05
Nodes (61): BillingExportModal(), BillingExportModalProps, Format, FORMATS, BillingRecordFilters(), BillingRecordFiltersProps, ProfileOption, ProfilePicker() (+53 more)

### Community 7 - "schemas/attendance.py"
Cohesion: 0.10
Nodes (27): AddToSessionRequestSchema, AddToSessionResponseSchema, AutoCheckoutRequestSchema, AutoCheckoutResponseSchema, CheckInRequestSchema, CheckInResponseSchema, CheckOutRequestSchema, CheckOutResponseSchema (+19 more)

### Community 8 - "tenant_required"
Cohesion: 0.07
Nodes (73): check_overdue(), create_expense(), create_payout(), create_plan(), delete_expense(), expense_categories(), expense_summary(), export_records() (+65 more)

### Community 9 - "ClassCardMenu.tsx"
Cohesion: 0.10
Nodes (37): ClassCardMenu(), EndClassModal(), FreeChip(), isRunning(), NoSessionTrigger(), RunningLight(), RunningLightState, serverMessage() (+29 more)

### Community 10 - "Student"
Cohesion: 0.05
Nodes (64): ActivityLog, Audit trail. Every significant action in the system is logged with user_id —…, Enrollment, Many-to-many: Student ↔ Class through Enrollment., A child enrolled in the academy., Student, check_out_student(), Check out a student from a session. (+56 more)

### Community 11 - "jwt_required"
Cohesion: 0.14
Nodes (20): add_student_to_session(), cancel_session(), create_session(), end_session(), get_day(), get_session_roster(), get_week(), jwt_required (+12 more)

### Community 12 - "User"
Cohesion: 0.07
Nodes (27): Verify a password against the stored hash., Whether this user may do ``need`` in ``area``. A thin reading of…, Every person who logs into the system. Owner or Staff., Hash a 4-digit PIN using bcrypt., Verify a PIN against the stored hash., User, change_password(), change_pin() (+19 more)

### Community 13 - "SessionMenu.tsx"
Cohesion: 0.10
Nodes (27): COMMISSION_TYPE_KEYS, CompensatoryModal(), CONFLICT_KIND_KEYS, conflictLabels(), dangerBtnCls, DangerConfirmModal(), EditSessionModal(), FreeNextModal() (+19 more)

### Community 14 - "SessionStudent"
Cohesion: 0.18
Nodes (14): Many-to-many: Session ↔ Student. Tracks attendance (is_present, check-in/out…, SessionStudent, auto_checkout_session(), Auto check-out all present students when session ends. Returns count of…, end_session(), is_finished(), _log(), materialize_roster() (+6 more)

### Community 15 - "react-i18next"
Cohesion: 0.06
Nodes (49): react-i18next, react-router-dom, ProvidersProps, TOAST_COLORS, TOAST_ICONS, ToastContainer(), AuthGuard(), AuthScreen (+41 more)

### Community 16 - "Notification"
Cohesion: 0.21
Nodes (14): Notification, In-app toast notification / alert., create_notification(), get_unread_count(), list_notifications(), mark_all_read(), mark_read(), jwt_required (+6 more)

### Community 17 - "SessionDetail.tsx"
Cohesion: 0.10
Nodes (30): PINInput, PINInputProps, PinStep(), PinStepProps, AgendaBoard(), hexToRgba(), resolveOverlaps(), InfoChipProps (+22 more)

### Community 18 - "billing_service.py"
Cohesion: 0.03
Nodes (99): Expense, PayoutRecord, Student purchase of a Class offer (credit-based or time-based). Table name is…, Money owed to a teacher — either derived from a session, or recorded by hand.…, A school operating expense — money that left the academy. Deliberately its own…, StudentSubscription, _class_ids_for_teacher(), _collected_between() (+91 more)

### Community 19 - "schemas/settings.py"
Cohesion: 0.08
Nodes (36): PermissionGrantSchema, What a user may do — the resolved grant, not the stored column. Handed to the…, AcademyResponseSchema, AddStaffRequestSchema, AddStaffResponseSchema, AppearanceResponseSchema, AutomationsResponseSchema, BillingConfigResponseSchema (+28 more)

### Community 20 - "routes/settings.py"
Cohesion: 0.07
Nodes (52): _coerce_bool(), deactivate_staff(), delete_staff(), export_school(), get_academy(), get_activity_log(), get_appearance(), get_automations() (+44 more)

### Community 21 - "SchedulingModal.tsx"
Cohesion: 0.09
Nodes (37): CONFLICT_KIND_KEYS, conflictKinds(), errMsg(), GroupOption, inputCls, Mode, primaryBtnCls, REASON_KEYS (+29 more)

### Community 22 - "uiStore.ts"
Cohesion: 0.05
Nodes (48): zustand, TeachersPage, FinancesModal(), AddTeacherModal(), AddTeacherModalProps, COMMISSION_PLACEHOLDER, COMMISSION_SUFFIX_KEYS, COMMISSION_TYPE_KEYS (+40 more)

### Community 23 - "DashboardPage.tsx"
Cohesion: 0.08
Nodes (41): CalendarPage(), REASON_KEYS, STATUS_KEYS, CONFLICT_KIND_KEYS, errMsg(), GroupOption, inputCls, RoomOption (+33 more)

### Community 24 - "scratch_pdf_language_check.py"
Cohesion: 0.06
Nodes (33): Backend string catalogue. One entry per language, one entry per key, English…, _accepted_tags(), Vinta School OS — backend translations. Why the server translates anything at…, The language to write in, given a request's ``Accept-Language``. Accepts the…, Looks up backend strings for one language. Callable rather than a ``get``…, A translator for `language`, which may be a raw ``Accept-Language``., Language tags from an ``Accept-Language`` header, most wanted first. A browser…, resolve_language() (+25 more)

### Community 25 - "export_service.py"
Cohesion: 0.09
Nodes (30): PaymentLog, One record per billing cycle per student. Core billing entity., Individual payment transactions against a billing record., StudentBilling, export_data(), get_dashboard(), jwt_required, route (+22 more)

### Community 26 - "DayPicker.tsx"
Cohesion: 0.22
Nodes (12): NotificationBell(), relativeTime(), styleFor(), TYPE_STYLE, DayPicker(), DayPickerProps, sizeStyles, todayISO() (+4 more)

### Community 27 - "BillingConfig.tsx"
Cohesion: 0.06
Nodes (63): RosterEntry, SessionCheckInModal(), STATUS_CONFIG, StudentSearchResult, AppearanceProps, BillingConfig(), BillingConfigProps, BillingPreset (+55 more)

### Community 28 - "rate_limiter.py"
Cohesion: 0.50
Nodes (3): Rate limiting configuration for authentication endpoints., flask_limiter, flask_limiter_util

### Community 29 - "api.ts"
Cohesion: 0.06
Nodes (31): StudentsPage, AgingBucket, AgingEntry, BUCKET_COLORS, BUCKET_LABEL_KEYS, FinanceBreakdownProps, TAB_LABEL_KEYS, BILLING_MODEL_STYLE (+23 more)

### Community 30 - "env.py"
Cohesion: 0.09
Nodes (20): alembic, apscheduler_schedulers_background, init_scheduler(), Vinta School OS — APScheduler Setup Initializes and manages the background task…, Initialize APScheduler with all configured cron jobs. Called during application…, Gracefully shut down the scheduler., shutdown_scheduler(), get_engine() (+12 more)

### Community 31 - "routes/auth.py"
Cohesion: 0.10
Nodes (34): Vinta School OS — Auth Blueprint /api/auth — Login, Profile Selection, PIN…, ChangePinRequestSchema, CreateOwnerRequestSchema, CreateOwnerResponseSchema, CreateProfileRequestSchema, LoginRequestSchema, MeResponseSchema, Meta (+26 more)

### Community 32 - "TestAuthentication"
Cohesion: 0.11
Nodes (10): Wrong password should return 401., Non-existent email should return 401., Valid PIN with correct academy should return access token., Invalid PIN should return 401., Verify PIN without X-Academy-Id should return 400., Verify PIN with wrong academy should return 401., Protected routes should require JWT token., Test authentication flows. (+2 more)

### Community 33 - "ActivityLog.tsx"
Cohesion: 0.17
Nodes (10): ActivityLog, ActivityLogEntry, ActivityLogProps, ActivityRow(), ActivityRowProps, ICON_MAP, ICON_STYLE, RelativeTime (+2 more)

### Community 34 - "TestCheckInFlow"
Cohesion: 0.08
Nodes (18): integration, Test session roster operations., New session should have empty roster., Should be able to add a student to a session roster., Adding the same student twice should return existing record., Test auto-checkout trigger., Test student check-in to session., Auto-checkout should check out all present students. (+10 more)

### Community 35 - "TestSessionCRUD"
Cohesion: 0.07
Nodes (17): integration, Should update session date via PATCH., Moved session times should snap to 5-minute grid., Should cancel a session via DELETE., Test recurring schedule → session generation., Test session create/read/update/delete via API., Creating a schedule should auto-generate sessions for 12 weeks., Should create a new session with valid data. (+9 more)

### Community 36 - "Academy Root Entity"
Cohesion: 0.11
Nodes (18): Attendance Blueprint (/api/attendance), Billing & Subscriptions Blueprint (/api/billing), Calendar & Sessions Blueprint (/api/sessions), Classes & Groups Blueprint (/api/classes), Students Blueprint (/api/students), Teachers Blueprint (/api/teachers), Session Attendance & Check-in/out Flow, Student Tuition & Credit/Time Billing Architecture (+10 more)

### Community 37 - "constants.ts"
Cohesion: 0.07
Nodes (27): ACADEMY_ID_KEY, ACTIVITY_TYPES, API_BASE_URL, AvatarPreset, BREAKPOINTS, CHART_COLORS, DEFAULT_SESSION_DURATION, ENTITY_FILTER_PAGES (+19 more)

### Community 38 - "compilerOptions"
Cohesion: 0.07
Nodes (26): compilerOptions, allowArbitraryExtensions, allowImportingTsExtensions, baseUrl, erasableSyntaxOnly, forceConsistentCasingInFileNames, ignoreDeprecations, isolatedModules (+18 more)

### Community 39 - "formatters.py"
Cohesion: 0.11
Nodes (20): _datetime(), days_until(), format_phone(), month_date_range(), next_occurrence(), now_utc(), parse_dzd(), Vinta School OS — Formatters & Helpers Phone (+213), Currency (DZD), Date/Time… (+12 more)

### Community 40 - "routes/students.py"
Cohesion: 0.10
Nodes (30): add_guardian(), bulk_enroll_students(), create_student(), delete_student(), enroll_student(), get_stats(), get_student(), list_guardians() (+22 more)

### Community 41 - "Class"
Cohesion: 0.06
Nodes (62): Class, Extensible palette entity for calendar subject colors., A subject offering (e.g., 'Math — CM2'). Enrollment target for students., Subject, Recurring weekly slot defining when a class meets., Schedule, _apply_group_fields(), create_class() (+54 more)

### Community 42 - "schemas/classes.py"
Cohesion: 0.12
Nodes (24): ClassListResponseSchema, ClassListSchema, ClassroomListResponseSchema, ClassroomSchema, CreateClassRequestSchema, CreateClassResponseSchema, CreateClassroomRequestSchema, CreateScheduleRequestSchema (+16 more)

### Community 43 - "academy_data_service.py"
Cohesion: 0.16
Nodes (18): _academy_owned_tables(), _collect(), collect_academy_keys(), _delete(), _delete_where(), _foreign_keys(), _primary_key(), purge_academy_data() (+10 more)

### Community 44 - "create_profile"
Cohesion: 0.18
Nodes (24): arguments, change_pin(), create_owner(), create_profile(), get_current_user(), get_profiles(), login(), logout() (+16 more)

### Community 45 - "Luxury School OS Concept"
Cohesion: 0.12
Nodes (17): Flask REST API Architecture, Auth Blueprint (/api/auth), Two-Stage Auth & Profile PIN Verification Flow, Docker Compose Local Environment, Flask & SQLAlchemy Dependencies, PIN-Attributed Activity Log & Audit Trail, Algerian Private Academy Target Market, Glassmorphic Design Tokens (--gold / --emerald) (+9 more)

### Community 46 - "test_session_start_and_close.py"
Cohesion: 0.13
Nodes (25): close_past_temporary_sessions(), Close out one-off classes whose day passed without ever being started.…, close_past_temporary_sessions(), Close out one-off classes whose day passed without ever being started. The rule…, Vinta School OS — starting a class, and closing out one that never ran. Two…, The guard must not break double-clicks or the repair path. A class already…, A one-off class whose day passed unstarted is over, and must stop being counted…, Cancelled, never conducted — the money decision. ``conducted`` is what the… (+17 more)

### Community 47 - "GlobalSearch.tsx"
Cohesion: 0.22
Nodes (10): classMatches(), classRow(), GlobalSearch(), Row, ROW_STYLE, SECTION_ORDER, STUDENT_STATUS_KEY, studentRow() (+2 more)

### Community 48 - "schemas/teachers.py"
Cohesion: 0.14
Nodes (19): CreateTeacherRequestSchema, CreateTeacherResponseSchema, PayrollSummarySchema, Schema, Teacher schemas — CRUD, Contracts, Payroll., POST /api/teachers response., PUT /api/teachers/<id>, Single teacher in list. (+11 more)

### Community 49 - "import_service.py"
Cohesion: 0.11
Nodes (35): _amount(), _build_context(), candidates_for(), _decode(), detect_dataset(), _digits(), _import_activity_logs(), _import_billing_records() (+27 more)

### Community 50 - "ClassQuickCreate.tsx"
Cohesion: 0.15
Nodes (20): load(), buildClassPayload(), CLASS_COLOR_PRESETS, ClassBillingFields(), classCancelBtnCls, ClassFormValues, classInputCls, classLabelCls (+12 more)

### Community 51 - "index.ts"
Cohesion: 0.05
Nodes (37): DIRECTION, initialLanguage, LANGUAGE_LABELS, Namespace, NAMESPACES, resources, SUPPORTED_LANGUAGES, vinta_school_os_src_i18n_locales_ar_auth (+29 more)

### Community 52 - "test_cron_jobs.py"
Cohesion: 0.19
Nodes (17): auto_checkout_expired_sessions(), Check all in-progress sessions whose end_time has passed and auto check-out any…, _make_session(), Vinta School OS — the end-of-class cron sweep. Regression cover for two bugs…, A class that has not ended yet is left alone., A ``scheduled`` class that nobody started is the desk's to cancel. The old…, A finished class is not re-processed., A session on a given day, in a given lifecycle state. (+9 more)

### Community 53 - "TestTenantIsolation"
Cohesion: 0.20
Nodes (7): integration, Ensure cross-academy access is blocked., Helper to create a second academy for cross-tenant testing., Student list should only return students from the authenticated academy., Students should be accessible with correct academy header., Request without X-Academy-Id should return 400., TestTenantIsolation

### Community 54 - "Session"
Cohesion: 0.09
Nodes (42): DayView(), DayViewProps, decimalToTime(), snapHour(), toCalendarSession(), yToTime(), FinalizeSessionModalProps, SchedulingModalProps (+34 more)

### Community 55 - "TimePicker.tsx"
Cohesion: 0.29
Nodes (9): Column(), formatLabel(), HOURS, minutesFor(), parse(), sizeStyles, TimePicker(), TimePickerProps (+1 more)

### Community 56 - "compilerOptions"
Cohesion: 0.12
Nodes (16): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, noEmit, noFallthroughCasesInSwitch (+8 more)

### Community 57 - "sys"
Cohesion: 0.08
Nodes (31): main(), Schema step — expenses.quantity. WHY §11 of the billing brief asks an owner to…, Resolve the SQLite file the app actually opens, from DATABASE_URL., resolve_db_path(), main(), Additive migration — billing relations, session lifecycle, billing toggles.…, Resolve the SQLite file the app actually opens, from DATABASE_URL., resolve_db_path() (+23 more)

### Community 58 - "record_checkin_billing_side_effects"
Cohesion: 0.08
Nodes (35): add_to_session(), auto_checkout(), check_in(), check_out(), complete_session(), get_roster(), guest_check_in(), jwt_required (+27 more)

### Community 59 - "package.json"
Cohesion: 0.04
Nodes (44): axios, clsx, oxlint, ref_path, tailwind-merge, tailwindcss, @tailwindcss/vite, @types/node (+36 more)

### Community 60 - "routes/calendar.py"
Cohesion: 0.19
Nodes (16): Vinta School OS — Calendar Blueprint /api/calendar, /api/sessions — Week/Month…, CreateSessionRequestSchema, CreateSessionResponseSchema, DaySessionsResponseSchema, Schema, Calendar schemas — Session CRUD, Week/Day views, Drag-and-drop., PATCH /api/sessions/<id>, Single session in calendar view. (+8 more)

### Community 61 - "academy_rules.py"
Cohesion: 0.14
Nodes (19): absence_consumes_credit(), count_gap_sessions(), default_teacher_share_percentage(), early_payment_on_extra_sessions(), free_session_auto_present(), Vinta School OS — Academy Rules Per-academy policy, read at the moment a…, The academy's default teacher share of gross, as a whole percent (0–100). The…, The academy's settings row, or None if it has never been created. (+11 more)

### Community 62 - "Session"
Cohesion: 0.04
Nodes (74): Immutable revenue fact per conducted session allocation (DZD integers)., RevenueEntry, A concrete class session on a specific date. Generated from Schedule or created…, Session, Junction table for teacher-subject many-to-many relationship., Monthly payroll record for each teacher., An instructor employed by the academy., Records when a teacher's hours are logged (per session). (+66 more)

### Community 63 - "app/config.py"
Cohesion: 0.19
Nodes (12): BaseConfig, DevelopmentConfig, ProductionConfig, Vinta School OS — Configuration Environments Dev, Test, and Production…, Shared configuration across all environments., Development environment configuration., Test environment configuration., Production environment configuration. (+4 more)

### Community 64 - "formatters.ts"
Cohesion: 0.05
Nodes (76): i18next, BillingCalendarCard(), BillingCalendarCardProps, CYCLE_STATUS_KEYS, statusDot(), activeLocale(), BillingSummaryCard(), BillingSummaryCardProps (+68 more)

### Community 65 - "class.ts"
Cohesion: 0.10
Nodes (19): addMinutes(), EXTEND_MINUTES, ExtendResult, extendSession(), AttendanceStatus, CheckInRequest, ClassBillingInfo, Classroom (+11 more)

### Community 66 - "add_staff"
Cohesion: 0.13
Nodes (17): Canonical form of an email address, for storage and for lookup. Login resolves…, add_staff(), Add a new staff profile (requires the staff permission + the caller's PIN).…, Update a staff profile — name, phone, login address, password, permissions.…, update_staff(), authenticate_credentials(), clean_email(), clean_password() (+9 more)

### Community 67 - "_session_user"
Cohesion: 0.25
Nodes (8): authenticate_profile(), get_current_user(), get_session_identity(), Authenticate a profile (owner or staff) with PIN. Returns tokens dict on…, The identity payload for a signed-in user, or ``None`` if there is none.…, The identity that travels with a token, in the client's own shape. Sent on…, Get the current authenticated user., _session_user()

### Community 68 - "school_export_service.py"
Cohesion: 0.10
Nodes (20): build_school_archive(), _cell(), _database_snapshot(), _iter_rows(), _jsonable(), Vinta School OS — School Export ("everything" archive) One download that…, Yield the named rows, in primary-key batches. Batched because a busy academy's…, A consistent copy of the SQLite database, or None on another engine.… (+12 more)

### Community 69 - "create_app"
Cohesion: 0.11
Nodes (17): create_app(), check_if_token_revoked(), Register all API blueprints., Application factory pattern., Register shell context objects., _register_blueprints(), _register_shell_context(), make_shell_context() (+9 more)

### Community 70 - "launcher.py"
Cohesion: 0.13
Nodes (24): bundle_dir(), choose_port(), configure_environment(), install_dir(), load_or_create_secrets(), looks_like_our_app(), main(), port_is_free() (+16 more)

### Community 71 - "App.tsx"
Cohesion: 0.40
Nodes (4): App(), Providers(), AppRouter(), vinta_school_os_src_styles_globals

### Community 72 - "token_blacklist.py"
Cohesion: 0.33
Nodes (5): blacklist_token(), cleanup_expired(), Simple in-memory token blacklist for JWT revocation. For production, replace…, Add a token JTI to the blacklist., Remove expired entries from the blacklist.

### Community 73 - "permissions.py"
Cohesion: 0.18
Nodes (22): Any, allowed(), allowed_any(), catalogue(), _clean_actions(), _clean_levels(), describe(), effective() (+14 more)

### Community 74 - "Guardian"
Cohesion: 0.22
Nodes (11): Guardian, Student guardian / emergency contact. One student can have multiple guardians., pick(), One element of ``seq``, chosen from ``rng``., _guardian_name(), _join_date(), s04_students — the roll: 489 students and the people to ring in an emergency.…, A deterministic intake date somewhere in the last twelve months. (+3 more)

### Community 75 - "test_cancel_session.py"
Cohesion: 0.16
Nodes (21): cancel_session(), Cancel a session, recording *why*. The reason is not decoration:…, Vinta School OS — cancelling a session. ``cancel_session`` is reached from…, CANCEL_REASONS is a plain Python tuple; the column is a native enum that knows…, An unrecognised reason is a label problem, not a reason to lose the cancel., A bare DELETE still cancels; it just does not claim to know why., Tenant scoping — the lookup is by id AND academy., A class that has not run can be called off; a class that is running can be… (+13 more)

### Community 76 - "seed/run.py"
Cohesion: 0.15
Nodes (21): log(), ``print`` that survives a cp1252 console. ``seed/run.py`` reconfigures stdout…, Where the database goes, _assert_deletable(), _assert_target(), _build_parser(), _force_utf8_stdout(), _local_db_path() (+13 more)

### Community 77 - "register_error_handlers"
Cohesion: 0.17
Nodes (3): Vinta School OS — Standardized JSON Error Handlers Consistent error response…, Register global error handlers for the Flask application., register_error_handlers()

### Community 78 - "overdue_bucket"
Cohesion: 0.24
Nodes (7): overdue_bucket(), Classify overdue days into aging buckets: 1-7d → 'recent', 8-30d → 'aging',…, Test aging bucket classification., 1-7 days overdue should be classified as 'recent'., 8-30 days overdue should be classified as 'aging'., 30+ days overdue should be classified as 'critical'., TestAgingBuckets

### Community 79 - "ClassesPage.tsx"
Cohesion: 0.15
Nodes (19): AddClassroomModal(), AddCourseGroupModal(), cancelBtnCls, ClassroomList(), COLOR_PRESETS, inputCls, SUBJECT_OPTIONS, submitBtnCls (+11 more)

### Community 80 - "s01_academy.py"
Cohesion: 0.15
Nodes (18): hex_color(), A ``#rrggbb`` string drawn from the shared palette., email_slug(), phone(), pick_many(), seed.pools — deterministic text pools and pickers. Every helper here takes the…, ``k`` *distinct* elements of ``seq``, in random order. Raises ``ValueError`` if…, A plausible Algerian mobile number: ``+213`` then 9 digits, first 5/6/7. (+10 more)

### Community 81 - "SettingsPage.tsx"
Cohesion: 0.06
Nodes (61): AppShell(), Avatar, AvatarProps, getGradientForName(), getInitials(), gradientPairs, hashCode(), sizeConfig (+53 more)

### Community 82 - "marshmallow"
Cohesion: 0.29
Nodes (7): DashboardResponseSchema, Schema, Analytics schemas — Dashboard stats, Revenue chart, CSV export., GET /api/analytics/revenue-chart response., GET /api/analytics/dashboard response., RevenueChartResponseSchema, marshmallow

### Community 83 - "_sqlite_enable_foreign_keys"
Cohesion: 0.67
Nodes (3): Turn on foreign key enforcement for every SQLite connection as it opens.…, _sqlite_enable_foreign_keys(), listens_for

### Community 84 - "ClassDetail.tsx"
Cohesion: 0.12
Nodes (19): BillingBadge, BillingReading, ClassBillingStat(), fetchBilling(), ClassDetail(), COLOR_PRESETS, DAY_KEYS, DraftSlot (+11 more)

### Community 85 - "days_overdue"
Cohesion: 0.24
Nodes (7): days_overdue(), Calculate how many days overdue a due date is. 0 if not overdue., Should return 0 for future due dates., Should return 0 when due date is today., Test days overdue calculation., Should return positive number for past due dates., TestDaysOverdue

### Community 86 - "TestBillingStatusDerivation"
Cohesion: 0.13
Nodes (10): unit, Test payment plan creation and properties., Payment plans should store correct values., Term plans should have 90-day duration., Test billing status derivation logic., Status should be 'paid' when paid_date is set and paid_amount >= amount_da., Status should be 'due' when due_date is in the future., Status should transition to 'overdue' when due_date has passed. (+2 more)

### Community 87 - "scratch_payout_chart_check.py"
Cohesion: 0.14
Nodes (7): Scratch smoke test for the new billing endpoints. Delete when done. Exercises,…, Owner-only enforcement, proven against the running dev server. Delete when…, Teacher cost in the monthly chart — before and after. Delete when done. The…, Live RBAC smoke test — drives the running dev server on :5000 the way the…, json, urllib_error, urllib_request

### Community 88 - "themeStore.ts"
Cohesion: 0.18
Nodes (18): applyDocumentLanguage(), Language, readStoredLanguage(), LANGUAGE_KEY, THEME_KEY, applyFontSize(), applyLanguage(), applyTheme() (+10 more)

### Community 89 - ".hash_password"
Cohesion: 0.13
Nodes (11): Set a new password hash (owner only)., Hash a password using bcrypt., Determinism, owner(), Create the owner profile for the test academy., Wrong password should fail., Staff without password_hash should return False., Test owner password hashing and verification. (+3 more)

### Community 90 - "helpers.py"
Cohesion: 0.15
Nodes (14): seed.config — every constant the seeder uses. Nothing here imports from…, bulk_insert(), _fill_primary_key(), month_iter(), parse_hhmm(), seed.helpers — shared utilities for every seed module. Kept deliberately small:…, Give ``obj`` a primary key if it has none yet. ``Session.bulk_save_objects``…, Insert many ORM objects in chunks, committing after each chunk. Wraps… (+6 more)

### Community 91 - ".oxlintrc.json"
Cohesion: 0.33
Nodes (5): plugins, rules, react/only-export-components, react/rules-of-hooks, $schema

### Community 93 - "TestHourlyPayroll"
Cohesion: 0.12
Nodes (12): unit, Settling a payroll should set paid_date and status., Test hourly contract payroll calculations., Hourly payroll = total_hours × hourly_rate., Payroll with zero hours should return 0 amount., Test per-student contract payroll calculations., Per-student payroll = active_students × per_student_rate., Test payroll status transitions. (+4 more)

### Community 94 - "build_review_build.py"
Cohesion: 0.27
Nodes (16): assemble(), build_frontend(), bundle_fonts(), freeze(), log(), main(), Path, Build the Vinta School OS offline review build. Produces a self-contained… (+8 more)

### Community 95 - "ClassGrid.tsx"
Cohesion: 0.19
Nodes (15): ClassCardMenuProps, ClassDetailProps, ClassCard(), ClassCardProps, ClassGrid(), ClassGridProps, resolveColor(), SkeletonCard() (+7 more)

### Community 96 - "Translation conventions — Vinta School OS"
Cohesion: 0.14
Nodes (13): auth(), Dates, numbers, currency, Do not translate, Finishing, Interpolation and plurals, Key naming, Languages, Namespaces (+5 more)

### Community 97 - "s06_sessions.py"
Cohesion: 0.20
Nodes (13): new_id(), A uuid4-shaped id drawn from ``rng``. Every model defaults its primary key to…, _at(), _dates_for(), _off_weekend(), s06_sessions — every class meeting, past, present and future. Owns: ``Session``…, Create sessions and attendance. Returns counts., Every date in ``[start, end]`` falling on ``day_of_week``. ``day_of_week`` is… (+5 more)

### Community 98 - "schemas/notifications.py"
Cohesion: 0.23
Nodes (11): CreateNotificationRequestSchema, CreateNotificationResponseSchema, NotificationListResponseSchema, NotificationSchema, Schema, Notification schemas — Toast alerts, Broadcasts., POST /api/notifications, GET /api/notifications response. (+3 more)

### Community 100 - "_session_duration_hours"
Cohesion: 0.50
Nodes (4): Session length in hours from start/end times (min 1h fallback)., _session_duration_hours(), Calculate session duration in hours from time objects., session_duration_hours()

### Community 107 - "DataImport.tsx"
Cohesion: 0.21
Nodes (10): ArchiveReport, DataImport(), DetectionFailure, failureOf(), FileReport, isArchive(), postFile(), Report (+2 more)

### Community 108 - "selfhost_fonts.py"
Cohesion: 0.27
Nodes (10): argparse, build_fonts(), fetch(), main(), patch_html(), Path, Bundle the frontend's webfonts into the app so it renders identically offline.…, Point the built index.html at the bundled fonts and tighten the CSP. (+2 more)

### Community 109 - "run"
Cohesion: 0.20
Nodes (9): _cycle_bounds(), How many classes one student takes, per ``CLASS_COUNT_MIX``., The current monthly cycle: first and last day of TODAY's month., Create the enrolments and subscriptions. Returns counts., run(), _record(), _weighted_count(), db() (+1 more)

### Community 110 - "teacherEmails.ts"
Cohesion: 0.36
Nodes (8): RFC-5322, currentAcademy(), isValidEmail(), listTeacherEmails(), loadAll(), saveAll(), setTeacherEmail(), TeacherEmailRecord

### Community 111 - "start_session"
Cohesion: 0.29
Nodes (7): LifecycleError, Exception, SCHEDULED -> IN_PROGRESS, and open the register. Returns ``(session,…, An illegal transition. ``status`` is the HTTP status the route returns., start_session(), The regression. A class eleven days out must stay a plan. Before the guard this…, test_future_class_cannot_be_started()

### Community 112 - "Vinta seeder"
Cohesion: 0.25
Nodes (7): ctx keys, Interface for later modules, Logins, Running it, Safety: vinta_dev.db, Vinta seeder, Which interpreter

### Community 113 - "scratch_permissions_check.py"
Cohesion: 0.29
Nodes (3): RBAC enforcement, proven end to end through the real app. Delete when done.…, The source of a `const NAME = { ... }` or `[ ... ]` literal., _ts_block()

### Community 114 - "scratch_i18n_verify.py"
Cohesion: 0.43
Nodes (6): check_file(), flatten(), load(), normalise(), Verify the three billing.json and the three settings.json dictionaries. Checks,…, key -> string, for every leaf.

### Community 122 - "Classroom"
Cohesion: 0.18
Nodes (13): Classroom, A physical room in the academy., _class_name(), _dedicated_time(), _pricing_pairs(), s03_classes — the weekly groups and their recurring slots. Owns: 28 weekly…, ``"Dim 10:00-12:00, Mer 14:00-16:00"`` from the reserved triples., Create the groups and schedules. Mutates ``ctx`` in place; returns counts. (+5 more)

### Community 123 - "list_sessions"
Cohesion: 0.40
Nodes (4): list_sessions(), List one group's sessions, soonest first. Query params: class_id required — the…, get_class_sessions(), Get one group's sessions, soonest first. A group's page needs its own sessions…

### Community 124 - "ImportDetectionError"
Cohesion: 0.40
Nodes (3): ImportDetectionError, A file that could not be read confidently — with what it might be., ValueError

### Community 125 - "update_session"
Cohesion: 0.50
Nodes (4): _duration_label(), Update a session. Body: { date?, start_time?, end_time?, is_free_session? } A…, How long the class runs, in the words the log should read. "1 h 45 min", not…, update_session()

### Community 126 - "MultiPaymentError"
Cohesion: 0.50
Nodes (3): MultiPaymentError, Exception, A multi-payment could not be recorded — nothing was charged. Raised instead of…

### Community 127 - "start.sh"
Cohesion: 0.50
Nodes (3): FLASK_APP, FLASK_ENV, start.sh script

### Community 128 - "Vite React TypeScript Architecture"
Cohesion: 0.67
Nodes (3): Vite React TypeScript Architecture, SPA HTML Entry Point, SVG Icon Sprite System

## Knowledge Gaps
- **462 isolated node(s):** `Meta`, `start.sh script`, `FLASK_APP`, `FLASK_ENV`, `$schema` (+457 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 1466 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **17 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `tenant_required()` connect `tenant_required` to `extensions.py`, `add_staff`, `routes/students.py`, `Class`, `jwt_required`, `User`, `Notification`, `routes/settings.py`, `export_service.py`, `record_checkin_billing_side_effects`, `list_sessions`, `routes/calendar.py`, `update_session`, `Session`?**
  _High betweenness centrality (0.043) - this node is a cross-community bridge._
- **Why does `User` connect `User` to `extensions.py`, `tenant_required`, `routes/settings.py`, `export_service.py`, `routes/auth.py`, `create_profile`, `import_service.py`, `TestTenantIsolation`, `record_checkin_billing_side_effects`, `Session`, `add_staff`, `_session_user`, `school_export_service.py`, `s01_academy.py`, `scratch_payout_chart_check.py`, `.hash_password`, `helpers.py`, `s06_sessions.py`, `run`, `scratch_permissions_check.py`?**
  _High betweenness centrality (0.036) - this node is a cross-community bridge._
- **Why does `cn()` connect `cn` to `react`, `billing.ts`, `ClassCardMenu.tsx`, `SessionMenu.tsx`, `react-i18next`, `SessionDetail.tsx`, `SchedulingModal.tsx`, `uiStore.ts`, `DashboardPage.tsx`, `DayPicker.tsx`, `BillingConfig.tsx`, `api.ts`, `ActivityLog.tsx`, `GlobalSearch.tsx`, `ClassQuickCreate.tsx`, `Session`, `TimePicker.tsx`, `formatters.ts`, `ClassesPage.tsx`, `SettingsPage.tsx`, `ClassDetail.tsx`, `ClassGrid.tsx`, `DataImport.tsx`?**
  _High betweenness centrality (0.025) - this node is a cross-community bridge._
- **Are the 3 inferred relationships involving `tenant_required()` (e.g. with `Academy` and `User`) actually correct?**
  _`tenant_required()` has 3 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Meta`, `start.sh script`, `FLASK_APP` to the rest of the system?**
  _462 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `extensions.py` be split into smaller, more focused modules?**
  _Cohesion score 0.045536445536445536 - nodes in this community are weakly interconnected._
- **Should `cn` be split into smaller, more focused modules?**
  _Cohesion score 0.04584942084942085 - nodes in this community are weakly interconnected._