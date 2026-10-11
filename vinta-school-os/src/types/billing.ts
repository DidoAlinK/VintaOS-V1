/**
 * Vinta School OS — Billing Types
 * Plans, subscriptions (credit + time), payouts, multi-pay receipts.
 */

// ============================================
// Payment Plan
// ============================================

export interface PaymentPlan {
  id: string
  academy_id: string
  name: string
  duration_days: number
  amount_da: number
  created_at: string
}

// ============================================
// Payment method (multi-pay modal)
// ============================================

export type PaymentMethod = 'CASH' | 'CCP' | 'BARIDI_MOB'

export const PAYMENT_METHOD_LABELS: Record<PaymentMethod, string> = {
  CASH: 'Cash',
  CCP: 'CCP',
  BARIDI_MOB: 'Baridi Mob',
}

// ============================================
// Subscription — per-student per-group credit/time shape
// ============================================

export type SubscriptionStatus =
  | 'ACTIVE'
  | 'EXPIRED'
  | 'DEPLETED'
  | 'EXPIRING_SOON'
  | 'RENEW_REQUIRED'
  | 'ATTENDANCE_WARNING'
  | 'SUSPENDED'

/**
 * A purchased subscription, as served by `GET /billing/subscriptions`.
 *
 * This is the record of money that actually changed hands — one row per
 * purchase, one group per row. A student's "plan" (what they are *on*) lives on
 * the group and is surfaced by `Student.plan`; do not read it from here.
 *
 * Note `group_name` here is the **class name** (`group.name`), whereas
 * `Student.group_name` is the short group label (`group.group_name`, e.g. "A").
 * Same words, different values — they are not interchangeable.
 */
export interface Subscription {
  id: string
  student_id: string
  student_name: string | null
  group_id: string
  group_name: string | null
  billing_model: 'CREDIT_BASED' | 'TIME_BASED'
  // Credit shape
  total_credits?: number | null
  remaining_credits?: number | null
  /** Credit window. Starts on purchase, ends at `cycle_deadline`. */
  cycle_start_date?: string | null
  /** ISO date the credit window closes. */
  cycle_deadline?: string | null
  // Time shape
  access_start_date?: string | null
  access_end_date?: string | null
  // Payment
  amount_paid_da?: number | null
  payment_method?: string | null
  status: SubscriptionStatus
  created_at: string | null
  updated_at?: string
}

// ============================================
// Student Billing
// ============================================

export interface StudentBilling {
  id: string
  student_id: string
  student_name: string
  payment_plan_id: string
  payment_plan_name: string
  amount_da: number
  status: 'paid' | 'due' | 'overdue'
  due_date: string
  paid_date?: string
  paid_amount?: number
  cycle_start: string
  cycle_end: string
  notes?: string
  created_at: string
  updated_at: string

  // Computed
  days_overdue: number
  aging_bucket: 'recent' | 'aging' | 'critical'
}

// ============================================
// Payment Log
// ============================================

export interface PaymentLog {
  id: string
  student_billing_id: string
  amount_da: number
  payment_method: string
  recorded_by: string
  recorded_by_name: string
  notes?: string
  created_at: string
}

// ============================================
// Revenue entry (analytics)
// ============================================

export interface RevenueEntry {
  id: string
  source: string
  amount_da: number
  recorded_at: string
  payment_method?: PaymentMethod
}

// ============================================
// Payout — per-teacher gross vs cut
// ============================================

export type PayoutStatus = 'PENDING' | 'PAID' | 'Pending' | 'Paid'

/**
 * Where a payout came from.
 *
 * `SESSION` — derived from a conducted session by the finalisation flow.
 * `MANUAL`  — entered by the owner: a bonus, a correction, an advance.
 */
export type PayoutSource = 'SESSION' | 'MANUAL'

/**
 * How a manually recorded payout was arrived at.
 *
 * The first three mirror the teacher's own `commission_type`, so a manual
 * payout is computed by the same rule as an automatic one. `CUSTOM` means the
 * owner stated a flat amount with no commission model behind it.
 */
export type PayoutBasis = 'PERCENTAGE' | 'FLAT_HOURLY' | 'FIXED_SESSION' | 'CUSTOM'

export interface PayoutRecord {
  id: string
  teacher_id: string
  teacher_name: string
  /** Absent on a manually recorded payout — it belongs to no session. */
  session_id?: string | null
  session_date?: string | null
  gross_revenue_da: number
  commission_type?: string
  commission_value?: number
  teacher_cut_da: number
  status: PayoutStatus
  paid_at?: string | null
  paid_by_staff_id?: string | null
  /** `SESSION` or `MANUAL`. */
  source?: PayoutSource
  /** Free note, shown in the payment-records archive. */
  notes?: string | null
  /** The day the payment is for; owner-chosen on a manual payout. */
  payout_date?: string | null
  /** When the row was written. This is the honest timestamp — `created_at`
   *  below has always meant the *session* date, not when money moved. */
  recorded_at?: string | null
  recorded_by_staff_id?: string | null
  /** The one date to show and sort under: session date, else payout date,
   *  else the day it was recorded. Computed server-side so the client never
   *  has to re-implement the fallback. */
  effective_date?: string | null
  /** Kept for backward compatibility. Prefer `effective_date`. */
  created_at: string
}

/**
 * Body of `POST /billing/payouts` — record a payout by hand.
 *
 * `amount_da` is the payout itself and is only read for `CUSTOM`; for the
 * other bases the server computes it from `gross_revenue_da`/`commission_value`
 * via the same function the session flow uses, so the two can never disagree.
 */
export interface CreatePayoutRequest {
  teacher_id: string
  basis: PayoutBasis
  amount_da?: number
  commission_value?: number
  gross_revenue_da?: number
  duration_hours?: number
  payout_date?: string | null
  notes?: string | null
  status: 'PENDING' | 'PAID'
  pin: string
}

// ============================================
// Payment records — the archive and its export
// ============================================

/** The three things that move money in an academy. */
export type BillingRecordKind = 'STUDENT_PAYMENT' | 'TEACHER_PAYOUT' | 'EXPENSE'

export type BillingRecordDirection = 'IN' | 'OUT'

/**
 * One row of the payment-records archive.
 *
 * Three genuinely different facts — a student's purchase, a teacher's payout
 * and a supplier's expense — unified at the API edge, because the question the
 * owner is asking ("what moved, and when?") spans all three.
 */
export interface BillingRecord {
  id: string
  kind: BillingRecordKind
  date: string | null
  profile_id: string | null
  profile_type: 'STUDENT' | 'TEACHER' | null
  profile_name: string | null
  label: string | null
  amount_da: number
  direction: BillingRecordDirection
  status: string | null
  method: string | null
  notes: string | null
  /** The mechanism behind the row: billing model, commission type, category. */
  detail?: string | null
  /** Payouts only: `SESSION` or `MANUAL`. */
  source?: PayoutSource
  commission_type?: string
  commission_value?: number
  gross_revenue_da?: number
}

export interface BillingRecordsTotals {
  money_in_da: number
  money_out_da: number
  net_da: number
}

export interface BillingRecordsResponse {
  records: BillingRecord[]
  count: number
  totals: BillingRecordsTotals
}

/**
 * The filter set shared by the archive and the export.
 *
 * One shape for both, so a filter that works on screen cannot silently mean
 * something else in the downloaded file.
 */
export interface BillingRecordFilters {
  from: string
  to: string
  /** A student or teacher id. Empty means "every profile". */
  profile: string
  /** Empty means every type. */
  type: '' | BillingRecordKind
  min_amount: string
  max_amount: string
}


// ============================================
// Multi-pay receipt — one student, several groups
// ============================================

export interface GroupCharge {
  group_id: string
  group_name: string
  amount_da: number
}

export interface MultiPayReceipt {
  id: string
  student_id: string
  student_name: string
  charges: GroupCharge[]
  total_da: number
  payment_method: PaymentMethod
  recorded_by?: string
  created_at: string
}

/**
 * Body of `POST /billing/subscriptions/pay`.
 *
 * This is the **amount received** shape, not the receipt shape above: the
 * caller sends one item per group being paid for, plus the total actually
 * collected. The backend snapshots `total_received` across the items and
 * allocates credits oldest-debt-first.
 */
export interface MultiPayRequest {
  student_id: string
  items: { group_id: string; amount: number }[]
  total_received: number
  payment_method: PaymentMethod
  pin: string
}

// ============================================
// Billing Stats
// ============================================

export interface BillingStats {
  // Student tuition
  student_total: number
  student_paid: number
  student_due: number
  student_overdue: number

  // Teacher payroll
  teacher_total: number
  teacher_pending: number
  teacher_settled: number
  teacher_overdue: number

  // Revenue
  month_income: number
  total_enrolled: number

  /** Default teacher share of a session's gross (0–100); school = remainder. */
  teacher_share_percentage?: number
}

export interface BillingRingData {
  name: string
  value: number
  color: string
}

// ============================================
// Revenue Chart
// ============================================

/**
 * One month of `GET /billing/revenue-chart`.
 *
 * Exactly the three fields the endpoint sends. This interface used to also
 * declare `paid`, `overdue`, `enrollments`, `withdrawals`, `hours`,
 * `students_per_teacher` and `avg_revenue` — none of which the endpoint has
 * ever returned. The revenue chart offered them in its property picker, so
 * choosing one drew an empty series that read as "no revenue". Naming only
 * what arrives makes that mistake a compile error instead of a blank chart.
 */
export interface RevenueDataPoint {
  month: string
  income: number
  overdue_count: number
}

/**
 * One bucket of the income chart, from `GET /billing/income-chart`.
 *
 * `label` is the server's own short form of the bucket ("%d %b" for a week,
 * "Oct 2026" for a month) and is deliberately NOT re-derived here: the bucket
 * boundary is the server's, and re-labelling it in the browser is how the
 * label and the money stop describing the same seven days.
 *
 * `has_data` is false for the weeks before the academy's first payment. The
 * chart draws those as gaps rather than as zeroes — "no money that week" and
 * "the school did not exist that week" are different claims, and a row of
 * zero-height bars implies the first.
 */
export interface IncomePoint {
  label: string
  income: number
  has_data: boolean
  week_start?: string
  week_end?: string
}

export interface IncomeChartResponse {
  period: 'weekly' | 'monthly'
  points: IncomePoint[]
}

// ============================================
// Teacher payments — what is owed, and to whom
// ============================================

/** One group's share of a teacher's total. The rows sum to the teacher's own figure. */
export interface TeacherPaymentGroup {
  group_id: string | null
  group_name: string | null
  gross_revenue_da: number
  teacher_cut_da: number
  pending_da: number
  paid_da: number
  session_count: number
  /** Sum of the group's session lengths, in hours. */
  duration_hours: number
}

/**
 * A teacher's earnings across **all** their groups, from
 * `GET /billing/teacher-payments`.
 *
 * `owed_da` / `settled_da` are the server's aliases for `pending_da` /
 * `paid_da` — the same columns under the names the confirmation flow talks in.
 * Read one pair or the other, never mix them, or the two will eventually
 * disagree on screen.
 */
export interface TeacherPayment {
  teacher_id: string
  teacher_name: string | null
  gross_revenue_da: number
  teacher_cut_da: number
  pending_da: number
  paid_da: number
  session_count: number
  /**
   * Total teaching time across every session that has a payout record, in
   * hours. Derived from start/end times by the same helper the finalisation
   * flow uses, so this is billable time and not an estimate.
   */
  duration_hours: number
  pending_count: number
  paid_count: number
  owed_da: number
  settled_da: number
  group_count: number
  student_count: number
  groups: TeacherPaymentGroup[]
}

// ============================================
// School expenses
// ============================================

/**
 * An operating expense, from `GET /billing/expenses`.
 *
 * `category` and `payment_method` are enum keys, not display text — the
 * label is looked up from the dictionary at render, so an unmapped value can
 * never reach the screen raw. The full accepted sets come from
 * `GET /billing/expense-categories` rather than being copied here, so the
 * form cannot offer a category the server will reject.
 */
export interface Expense {
  id: string
  category: string
  label: string
  amount_da: number
  /** Unit count when the expense came in units; null when not stated. */
  quantity: number | null
  expense_date: string | null
  vendor: string | null
  payment_method: string
  notes: string | null
  created_at: string | null
}

/** Body of `POST /billing/expenses` and `PUT /billing/expenses/<id>`. */
export interface ExpenseInput {
  category: string
  label: string
  amount_da: number
  expense_date: string
  quantity?: number | null
  vendor?: string | null
  payment_method?: string
  notes?: string | null
}

export interface ExpenseCategoryTotal {
  category: string
  amount_da: number
}

export interface ExpenseMethodTotal {
  payment_method: string
  amount_da: number
}

export interface ExpenseSeriesPoint {
  month: string
  expense: number
}

export interface ExpenseSummary {
  /** Every expense on record, regardless of the requested window. */
  total_da: number
  /** Only the expenses inside the requested window. */
  window_total_da: number
  count: number
  by_category: ExpenseCategoryTotal[]
  by_method: ExpenseMethodTotal[]
  series: ExpenseSeriesPoint[]
}

export interface ExpenseCategories {
  categories: string[]
  payment_methods: string[]
}

// ============================================
// Financial summary — revenue, teacher cost, expenses, net profit
// ============================================

export interface FinancialSeriesPoint {
  month: string
  revenue: number
  teacher_cost: number
  expense: number
  net: number
}

/**
 * The academy's headline figures, from `GET /billing/financial-summary`.
 *
 * `net_profit_da = revenue − teacher cost − expenses`, with every term read
 * from the table that owns it. Teacher cost counts the cut a conducted
 * session earned, settled or not — the class ran, so the money is owed; how
 * much of it has actually left is `teacher_paid_da` / `teacher_pending_da`.
 */
export interface FinancialSummary {
  revenue_total_da: number
  teacher_cost_total_da: number
  teacher_paid_da: number
  teacher_pending_da: number
  expenses_total_da: number
  net_profit_da: number
  /** The academy's stored teacher/school split; the school's share is 100 − this. */
  teacher_share_percentage: number
  series: FinancialSeriesPoint[]
}

export interface SubjectRevenue {
  subject: string
  amount: number
  color: string
}

// ============================================
// Billing Requests
// ============================================

export interface CreatePaymentPlanRequest {
  name: string
  duration_days: number
  amount_da: number
}

export interface RecordPaymentRequest {
  student_billing_id: string
  amount_da: number
  payment_method: string
  notes?: string
}

// ============================================
// Aging Bucket
// ============================================

export interface AgingBucket {
  range: string
  count: number
  total_amount: number
  students: {
    student_id: string
    student_name: string
    amount: number
    days_overdue: number
  }[]
}

// ============================================
// Billing State
// ============================================

export interface BillingState {
  plans: PaymentPlan[]
  stats: BillingStats
  overdueList: StudentBilling[]
  revenueData: RevenueDataPoint[]
  isLoading: boolean
  error: string | null

  // Actions
  fetchPlans: () => Promise<void>
  createPlan: (data: CreatePaymentPlanRequest) => Promise<PaymentPlan>
  fetchStats: () => Promise<void>
  fetchOverdue: () => Promise<void>
  fetchRevenue: (property: string) => Promise<void>
  recordPayment: (data: RecordPaymentRequest) => Promise<PaymentLog>
  getStudentBilling: (studentId: string) => Promise<StudentBilling[]>
}
