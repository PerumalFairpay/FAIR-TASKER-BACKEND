"""
Comprehensive Collection Catalog and Semantic Intent Dictionary for Fyro AI (Fair-Tasker HRM).
Covers all queryable MongoDB collections across HRM, Attendance, Leave, Projects, Payroll, Assets, and Docs.
Provides canonical descriptions, keyword intent mappings ('use_for'), anti-hallucination rules ('avoid_for'),
access scopes ('access': 'public' | 'personal' | 'admin_only'), and related collection linkages.
"""

from typing import Dict, Any, List
import re


COLLECTION_CATALOG: Dict[str, Dict[str, Any]] = {
    # =========================================================================
    # 1. EMPLOYEES & ORGANIZATION
    # =========================================================================
    "employees": {
        "description": "Employee master records: full_name, employee_no_id, email, mobile, designation, department, role, work_mode, employee_type, status, shift_id, date_of_joining, gender, marital_status, reporting_manager, and leave balances.",
        "use_for": [
            "employee details", "my profile", "my details", "employee list", "staff directory",
            "designation", "department members", "work mode", "onboarding status", "employee count",
            "joining date", "reporting manager", "who works in"
        ],
        "avoid_for": "Portal login credentials or system accounts (use `users` for admin-only user accounts).",
        "related_collections": ["departments", "shifts", "leave_requests", "attendance"],
        "access": "personal",
    },
    "departments": {
        "description": "Organization departments: name, description, head_of_department, default_shift_id.",
        "use_for": ["departments", "department list", "company departments", "team structure"],
        "related_collections": ["employees", "shifts"],
        "access": "public",
    },
    "shifts": {
        "description": "Work shift definitions: name, start_time, end_time, grace_period, working_days.",
        "use_for": ["shifts", "shift timings", "work hours", "shift schedule", "office timing"],
        "related_collections": ["employees", "departments", "attendance"],
        "access": "public",
    },
    "users": {
        "description": "System login accounts for portal users: name, email, role, employee_no_id, status.",
        "use_for": ["portal users", "login accounts", "system users", "user roles"],
        "avoid_for": "HR employee profiles and leave/attendance details (use `employees` instead).",
        "related_collections": ["employees", "roles"],
        "access": "admin_only",
    },
    "roles": {
        "description": "Role definitions for RBAC access control: name, description.",
        "use_for": ["roles", "access roles", "permission roles"],
        "related_collections": ["users"],
        "access": "admin_only",
    },

    # =========================================================================
    # 2. ATTENDANCE, LEAVES, WFH & HOLIDAYS
    # =========================================================================
    "attendance": {
        "description": "Daily attendance punch logs: employee_id, date (YYYY-MM-DD), clock_in, clock_out, status (Present, Late, Half Day, Absent, On Leave, WFH), total_hours, break_duration, shift_id.",
        "use_for": [
            "attendance", "clock in", "clock out", "punch in", "check in", "late arrivals",
            "absent", "present today", "worked hours", "timesheet", "my attendance"
        ],
        "avoid_for": "Leave applications (use `leave_requests`) or WFH applications (use `wfh_requests`).",
        "related_collections": ["employees", "shifts"],
        "access": "personal",
    },
    "leave_requests": {
        "description": "Employee leave applications: employee_id, leave_type_id, start_date, end_date, number_of_days, reason, status (Pending, Approved, Rejected, Cancelled), approved_by.",
        "use_for": [
            "leave requests", "leaves", "pending leaves", "approved leaves", "time off",
            "vacation", "sick leave", "casual leave", "my leaves", "who is on leave"
        ],
        "avoid_for": "Leave policy definitions / annual quota (use `leave_types`) or WFH requests (use `wfh_requests`).",
        "related_collections": ["employees", "leave_types"],
        "access": "personal",
    },
    "leave_types": {
        "description": "Master leave type definitions: name (e.g., Casual Leave, Sick Leave), number_of_days, carry_forward, description.",
        "use_for": ["leave types", "leave policy", "annual leave quota", "types of leave", "leave rules"],
        "related_collections": ["leave_requests"],
        "access": "public",
    },
    "wfh_requests": {
        "description": "Work From Home (WFH) requests: employee_id, date / start_date, end_date, reason, status (Pending, Approved, Rejected).",
        "use_for": ["wfh", "work from home", "remote work requests", "my wfh"],
        "related_collections": ["employees"],
        "access": "personal",
    },
    "holidays": {
        "description": "Company holiday calendar: name, date (YYYY-MM-DD), type, description.",
        "use_for": ["holidays", "public holidays", "upcoming holidays", "holiday calendar", "next holiday"],
        "related_collections": [],
        "access": "public",
    },

    # =========================================================================
    # 3. TASKS, PROJECTS, EOD REPORTS & CLIENTS
    # =========================================================================
    "tasks": {
        "description": "Project/work tasks: title, description, project_id, assigned_to (list of employee IDs), status, priority, due_date, estimated_hours.",
        "use_for": ["tasks", "my tasks", "assigned tasks", "pending tasks", "overdue tasks", "task status"],
        "related_collections": ["projects", "employees", "eod_reports"],
        "access": "personal",
    },
    "projects": {
        "description": "Company projects: name, description, client_id, team_members (list of employee IDs), status, start_date, end_date.",
        "use_for": ["projects", "my projects", "active projects", "project team", "project list"],
        "related_collections": ["tasks", "clients", "employees"],
        "access": "personal",
    },
    "eod_reports": {
        "description": "End-of-Day (EOD) work reports: task_id, project_id, assigned_to (list of employee IDs), date, summary, hours_spent, status.",
        "use_for": ["eod", "eod reports", "daily report", "end of day report", "work log"],
        "related_collections": ["tasks", "projects"],
        "access": "personal",
    },
    "clients": {
        "description": "External clients: name, email, phone, company, address, status.",
        "use_for": ["clients", "client list", "customers"],
        "related_collections": ["projects"],
        "access": "admin_only",
    },

    # =========================================================================
    # 4. PAYROLL & EXPENSES
    # =========================================================================
    "payslips": {
        "description": "Monthly employee payslips: employee_id, month, year, basic_salary, allowances, deductions, net_salary, status.",
        "use_for": ["payslip", "salary slip", "my salary", "paycheck", "net pay", "monthly pay"],
        "related_collections": ["employees", "payslip_components"],
        "access": "personal",
    },
    "payslip_components": {
        "description": "Master salary/payslip earning and deduction component definitions: name, type (Earning/Deduction), calculation_type.",
        "use_for": ["payslip components", "salary components", "allowances", "deductions"],
        "related_collections": ["payslips"],
        "access": "admin_only",
    },
    "expenses": {
        "description": "Company operational expenses: expense_category_id, amount, purpose, payment_mode, date.",
        "use_for": ["expenses", "company expenses", "spending", "expense report"],
        "related_collections": ["expense_categories"],
        "access": "admin_only",
    },
    "expense_categories": {
        "description": "Master categories for company expenses: name, description.",
        "use_for": ["expense categories"],
        "related_collections": ["expenses"],
        "access": "admin_only",
    },

    # =========================================================================
    # 5. ASSETS
    # =========================================================================
    "assets": {
        "description": "Company IT/office assets: name, asset_tag, serial_number, category_id, assigned_to (employee ID), status, purchase_date.",
        "use_for": ["assets", "my assets", "assigned laptop", "equipment", "company devices", "inventory"],
        "related_collections": ["asset_categories", "employees"],
        "access": "personal",
    },
    "asset_categories": {
        "description": "Master asset categories: name, description.",
        "use_for": ["asset categories", "equipment types"],
        "related_collections": ["assets"],
        "access": "public",
    },

    # =========================================================================
    # 6. DOCUMENTS, BLOGS, TICKETS & FEEDBACK
    # =========================================================================
    "documents": {
        "description": "Company policy documents and files metadata: title, description, category_id, status (Active/Inactive), file_url.",
        "use_for": ["documents", "policy files", "company handbooks", "document list"],
        "avoid_for": "Searching inside the actual text of a policy/manual (use `search_document_content` tool instead).",
        "related_collections": ["document_categories"],
        "access": "public",
    },
    "document_categories": {
        "description": "Categories for company documents: name, description.",
        "use_for": ["document categories", "policy categories"],
        "related_collections": ["documents"],
        "access": "public",
    },
    "blogs": {
        "description": "Company blog posts and internal announcements: title, content, author, tags, published_at.",
        "use_for": ["blogs", "announcements", "company news", "posts", "updates"],
        "related_collections": [],
        "access": "public",
    },
    "tickets": {
        "description": "Internal support/IT/HR helpdesk tickets: title, description, category, priority, status, requester_id, assigned_to.",
        "use_for": ["tickets", "support tickets", "helpdesk", "my tickets", "open tickets"],
        "related_collections": ["employees"],
        "access": "personal",
    },
    "feedback": {
        "description": "Employee feedback submissions: user_id, rating, category, comment, created_at.",
        "use_for": ["feedback", "my feedback", "suggestions"],
        "related_collections": [],
        "access": "personal",
    },
}


def get_collection_catalog_summary(allowed_collections: List[str]) -> str:
    """Returns a compact catalog summary for the collections the current user may query."""
    lines = []
    allowed_set = set(allowed_collections)
    for col_name, meta in COLLECTION_CATALOG.items():
        if col_name not in allowed_set:
            continue
        desc = meta.get("description", "")
        avoid = meta.get("avoid_for", "")
        line = f"• `{col_name}`: {desc}"
        if avoid:
            line += f" (AVOID FOR: {avoid})"
        lines.append(line)
    return "\n".join(lines)


def find_collections_by_intent(query: str, allowed_collections: List[str], top_k: int = 5) -> List[str]:
    """Scores and returns the most relevant allowed collections for the user's query."""
    if not query:
        return []

    lower_query = query.lower()
    tokens = set(re.findall(r"[a-z0-9_]+", lower_query))
    stop_words = {
        "the", "is", "are", "was", "were", "a", "an", "of", "in", "on", "for", "to",
        "and", "or", "with", "me", "my", "i", "show", "get", "list", "give", "what",
        "who", "how", "many", "much", "all", "can", "you", "tell", "about", "find"
    }
    meaningful_tokens = [t for t in tokens if t not in stop_words and len(t) > 1]

    domain_synonyms = {
        "leave": ["leave_requests", "leave_types"],
        "leaves": ["leave_requests", "leave_types"],
        "pto": ["leave_requests", "leave_types"],
        "vacation": ["leave_requests", "leave_types"],
        "sick": ["leave_requests", "leave_types"],
        "casual": ["leave_requests", "leave_types"],
        "wfh": ["wfh_requests"],
        "remote": ["wfh_requests"],
        "attendance": ["attendance", "shifts"],
        "punch": ["attendance"],
        "clock": ["attendance"],
        "checkin": ["attendance"],
        "late": ["attendance"],
        "absent": ["attendance"],
        "present": ["attendance"],
        "salary": ["payslips", "payslip_components"],
        "payslip": ["payslips"],
        "pay": ["payslips"],
        "expense": ["expenses", "expense_categories"],
        "expenses": ["expenses", "expense_categories"],
        "task": ["tasks", "projects"],
        "tasks": ["tasks", "projects"],
        "project": ["projects", "tasks"],
        "projects": ["projects", "tasks"],
        "eod": ["eod_reports", "tasks"],
        "asset": ["assets", "asset_categories"],
        "assets": ["assets", "asset_categories"],
        "laptop": ["assets"],
        "device": ["assets"],
        "holiday": ["holidays"],
        "holidays": ["holidays"],
        "policy": ["documents", "document_categories"],
        "policies": ["documents", "document_categories"],
        "document": ["documents", "document_categories"],
        "documents": ["documents", "document_categories"],
        "blog": ["blogs"],
        "blogs": ["blogs"],
        "announcement": ["blogs"],
        "announcements": ["blogs"],
        "ticket": ["tickets"],
        "tickets": ["tickets"],
        "support": ["tickets"],
        "department": ["departments", "employees"],
        "departments": ["departments"],
        "shift": ["shifts", "attendance"],
        "shifts": ["shifts"],
        "employee": ["employees"],
        "employees": ["employees"],
        "staff": ["employees", "users"],
        "profile": ["employees"],
        "client": ["clients", "projects"],
        "clients": ["clients", "projects"],
        "feedback": ["feedback"],
    }

    expanded_tokens = list(meaningful_tokens)
    for tok in meaningful_tokens:
        if tok in domain_synonyms:
            expanded_tokens.extend(domain_synonyms[tok])

    allowed_set = set(allowed_collections)
    scores: Dict[str, float] = {}

    for col_name, meta in COLLECTION_CATALOG.items():
        if col_name not in allowed_set:
            continue
        score = 0.0
        col_lower = col_name.lower()
        desc_lower = meta.get("description", "").lower()
        use_list = [u.lower() for u in meta.get("use_for", [])]
        use_blob = " ".join(use_list)

        for use_phrase in use_list:
            if use_phrase in lower_query:
                score += 15.0

        for token in expanded_tokens:
            if token in col_lower:
                score += 8.0
            if token in use_blob:
                score += 4.0
            if token in desc_lower:
                score += 2.0

        avoid_text = (meta.get("avoid_for") or "").lower()
        if avoid_text:
            for token in meaningful_tokens:
                if token in avoid_text:
                    score -= 10.0

        if score > 0:
            scores[col_name] = score

    sorted_cols = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    top_cols = [col for col, _ in sorted_cols[:top_k]]

    final_cols = list(top_cols)
    for col in top_cols:
        for rel in COLLECTION_CATALOG.get(col, {}).get("related_collections", []):
            if rel in allowed_set and rel not in final_cols and len(final_cols) < (top_k + 3):
                final_cols.append(rel)

    return final_cols
