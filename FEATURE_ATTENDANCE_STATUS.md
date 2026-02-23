# Feature: Enhanced Attendance Status System

**Version:** 1.0  
**Date:** 2026-02-20  
**Status:** Planning

---

## Overview

Replace the simple attendance status (`Present`, `Absent`, `Leave`, `Holiday`) with a detailed, hierarchical system that gives accurate information about _how_ an employee was present or absent.

---

## Status Hierarchy

```
Attendance Status
├── Present
│   ├── Ontime         → Clocked in before Shift Start + Grace Period
│   ├── Late           → Clocked in after Shift Start + Grace Period
│   ├── Permission     → Late, but has an Approved Leave Request (type: Permission)
│   └── Half Day       → Attended only half shift (has Approved Half Day Leave)
├── Absent             → No clock-in, no leave, no holiday
├── Leave
│   ├── CL             → Casual Leave
│   ├── SL             → Sick Leave
│   ├── LOP            → Loss of Pay
│   ├── Half Day       → Approved Half Day Leave, no clock-in
│   └── <others>       → Any other leave types configured in system
└── Holiday            → Date is a system-configured Holiday
```

---

## Status Calculation Logic

### Priority Order (checked top-to-bottom)

| Priority | Condition                                                          | Resulting Status         |
| -------- | ------------------------------------------------------------------ | ------------------------ |
| 1        | Employee has clock-in AND Approved Leave (type: `Permission`)      | `Present` · `Permission` |
| 2        | Employee has clock-in AND Approved Half Day Leave                  | `Present` · `Half Day`   |
| 3        | Employee has clock-in AND clock-in > Shift Effective Start + Grace | `Present` · `Late`       |
| 4        | Employee has clock-in AND clock-in ≤ Shift Start + Grace           | `Present` · `Ontime`     |
| 5        | No clock-in AND Approved Full Day Leave (CL/SL/LOP...)             | `Leave` · `<type_code>`  |
| 6        | No clock-in AND Approved Half Day Leave                            | `Leave` · `Half Day`     |
| 7        | No clock-in AND Date is a Holiday                                  | `Holiday`                |
| 8        | No clock-in AND none of the above                                  | `Absent`                 |

---

## Half Day Calculation

### Mid-Shift Time Formula

```
Total Shift Duration  = Shift End Time - Shift Start Time
Mid-Shift Time        = Shift Start Time + (Total Shift Duration / 2)
```

**Example:**

- Shift: 09:00 → 18:00 (9 hours)
- Half Duration: 4 hours 30 minutes
- **Mid-Shift: 13:30**

### Clock-In/Clock-Out Rules

| Leave Session                                       | Expected Clock-In               | Expected Clock-Out          |
| --------------------------------------------------- | ------------------------------- | --------------------------- |
| **First Half Leave** (off morning, work afternoon)  | Mid-Shift Time (e.g. 13:30)     | Normal Shift End            |
| **Second Half Leave** (work morning, off afternoon) | Normal Shift Start (e.g. 09:00) | Mid-Shift Time (e.g. 13:30) |

- Late check applies from the **Effective Start Time** for that session.
- If late by more than **Grace Period** from the Effective Start → `Late` flag is set even on Half Day.

---

## Permission Logic

- `Permission` is an **Approved Leave Request** with `leave_duration_type = "Permission"`.
- It is used when an employee is late due to a pre-approved personal reason (doctor visit, errand, etc.).
- It does **NOT** deduct leave balance — it is purely a status marker.
- If the employee has an approved Permission request for the date but clocks in **before** shift start + grace, status remains `Present · Ontime` (no penalty).

---

## Database / Model Changes

### `attendance` Collection — New Fields

| Field               | Type   | Description                                                     |
| ------------------- | ------ | --------------------------------------------------------------- |
| `status`            | `str`  | Primary status: `Present`, `Absent`, `Leave`, `Holiday`         |
| `attendance_status` | `str`  | Detailed sub-status: `Ontime`, `Late`, `Permission`, `Half Day` |
| `is_late`           | `bool` | True if clocked in past grace period                            |
| `is_half_day`       | `bool` | True if approved half day leave exists                          |
| `is_permission`     | `bool` | True if approved permission leave exists                        |
| `leave_type_code`   | `str`  | Leave code: `CL`, `SL`, `LOP`, `Half Day`, etc.                 |

### `leave_requests` Collection — Update

- Add `"Permission"` to `leave_duration_type` allowed values.
  - Current: `"Single"`, `"Multiple"`, `"Half Day"`
  - New: `"Single"`, `"Multiple"`, `"Half Day"`, `"Permission"`

---

## Code Changes Required

### 1. `app/models.py`

- [ ] Add `attendance_status`, `is_permission`, `is_half_day`, `leave_type_code` to `AttendanceBase`.
- [ ] Update comment on `LeaveRequestBase.leave_duration_type` to include `"Permission"`.

### 2. `app/crud/repository.py`

#### `bulk_sync_biometric_logs`

- [ ] After finding the employee, check for approved Leave Requests on that date.
- [ ] Check for Holidays on that date.
- [ ] Apply priority logic from the table above to determine `status` and `attendance_status`.
- [ ] Calculate `mid_shift_time` from shift `start_time` and `end_time`.
- [ ] Set `is_late`, `is_half_day`, `is_permission`, `leave_type_code`.

#### `clock_in` (manual web/mobile)

- [ ] Apply the same status calculation logic on manual clock-in.

#### `get_dashboard_metrics`

- [ ] Update aggregation to count by `attendance_status` (not just `status`).
- [ ] Return detailed breakdown: `ontime`, `late`, `permission`, `half_day`, `absent`, `leave`, `holiday`.

#### `generate_attendance_for_date` (jobs)

- [ ] Apply priority logic when auto-generating daily attendance records:
  - Mark `Holiday` first.
  - Mark `Leave` from approved requests.
  - Mark `Absent` for remaining employees with no record.

### 3. `app/routes/attendance.py`

- [ ] No new endpoints needed.
- [ ] Return `attendance_status` along with `status` in all list/detail responses.

### 4. Frontend (`FAIR-TASKER`)

- [ ] Update attendance table/cards to display `attendance_status` as a badge.
- [ ] Update filters to allow filtering by `attendance_status`.
- [ ] Update dashboard metrics to show new breakdown.
- [ ] Add `"Permission"` as option in Leave Request form (`leave_duration_type`).

---

## Verification Checklist

| Scenario                                            | Expected Status | Expected Sub-Status   |
| --------------------------------------------------- | --------------- | --------------------- |
| Clock in at 08:55, shift starts 09:00 (grace 15min) | Present         | Ontime                |
| Clock in at 09:20, shift starts 09:00 (grace 15min) | Present         | Ontime (within grace) |
| Clock in at 09:30, shift starts 09:00 (grace 15min) | Present         | Late                  |
| Clock in at 09:30 + Permission request approved     | Present         | Permission            |
| Clock in at 13:30 + First Half Leave approved       | Present         | Half Day              |
| No clock-in + CL approved                           | Leave           | CL                    |
| No clock-in + Half Day Leave approved               | Leave           | Half Day              |
| No clock-in + Holiday                               | Holiday         | —                     |
| No clock-in + no leave/holiday                      | Absent          | —                     |

---

## Open Questions

- [ ] Should `Permission` deduct from any leave balance or be entirely free? _(Default: No deduction)_
- [ ] What is the configurable grace period for Half Day sessions? _(Default: Same as shift grace period)_
- [ ] Should weekends be auto-marked or ignored? _(Default: Ignored / No record)_
