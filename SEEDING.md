# Database Seeding Guide

This guide explains how to seed the FairTasker database with initial data.

## Overview

The seeding process populates the database with essential initial data including:

- **Permissions** (44 permissions)
- **Roles** (2 roles: admin, employee)
- **Leave Types** (8 types: CL, SL, EL, LOP, ML, PL, CO, PER)
- **Admin User** (1 default admin account)
- **Holidays** (10 sample holidays for 2026)

## Quick Start

### Option 1: Run All Seeds (Recommended)

To seed all data at once, run the master seed script inside the Docker container:

```bash
docker exec fairpay_hrm_backend python seed_all.py
```

### Option 2: Run Individual Seeds

You can also run individual seed scripts:

```bash
# Seed permissions and roles
docker exec fairpay_hrm_backend python seed_permissions.py

# Seed leave types
docker exec fairpay_hrm_backend python seed_leave_types.py

# Seed admin user
docker exec fairpay_hrm_backend python seed_admin.py

# Seed holidays
docker exec fairpay_hrm_backend python seed_holidays.py
```

## Default Admin Credentials

After seeding, you can log in with:

- **Email**: `admin@fairpay.com`
- **Password**: `admin123`

⚠️ **IMPORTANT**: Change the admin password immediately after first login!

## Seeded Data Details

### 1. Permissions (44 total)

Permissions are organized by modules:

- **Dashboard**: View Dashboard
- **Employee**: View, Create, Edit, Delete
- **Attendance**: View All, View Self, Manage
- **Leave**: View, Apply, Approve, Manage Types
- **Tasks**: View, Create, Edit, View EOD Reports
- **Projects**: View, Manage
- **Finance**: View All Expenses, Submit, Approve
- **Assets**: View, Manage
- **Documents**: Manage
- **Settings**: Holidays, Clients, Blogs
- **Navigation**: 13 navigation permissions for sidebar

### 2. Roles (2 total)

#### Admin Role

- Has **all 44 permissions**
- Full system access

#### Employee Role

- Limited permissions including:
  - View Dashboard
  - View Self Attendance
  - Apply for Leave
  - View Tasks and Projects
  - Submit Expenses
  - View Assets
  - View Employees
  - Navigation permissions for relevant sections

### 3. Leave Types (8 total)

| Code | Name             | Type   | Days/Year   | Monthly Allowed |
| ---- | ---------------- | ------ | ----------- | --------------- |
| CL   | Casual Leave     | Paid   | 12          | 1               |
| SL   | Sick Leave       | Paid   | 10          | 1               |
| EL   | Earned Leave     | Paid   | 15          | 2               |
| LOP  | Loss of Pay      | Unpaid | 365         | 0               |
| ML   | Maternity Leave  | Paid   | 180         | 0               |
| PL   | Paternity Leave  | Paid   | 5           | 0               |
| CO   | Compensatory Off | Paid   | 0 (accrued) | 0               |
| PER  | Permission       | Paid   | 12          | 2               |

### 4. Holidays (10 for 2026)

Sample Indian holidays:

- Republic Day (Jan 26)
- Holi (Mar 14)
- Good Friday (Apr 3)
- Eid al-Fitr (Apr 21)
- Independence Day (Aug 15)
- Janmashtami (Aug 25)
- Gandhi Jayanti (Oct 2)
- Dussehra (Oct 13)
- Diwali (Nov 1)
- Christmas (Dec 25)

## Verification

To verify the seeding was successful:

```bash
docker exec fairpay_hrm_db mongosh fairpay_hrm_db --quiet --eval "print('Users: ' + db.users.countDocuments()); print('Permissions: ' + db.permissions.countDocuments()); print('Roles: ' + db.roles.countDocuments()); print('Leave Types: ' + db.leave_types.countDocuments()); print('Holidays: ' + db.holidays.countDocuments());"
```

Expected output:

```
Users: 1
Permissions: 44
Roles: 2
Leave Types: 8
Holidays: 10
```

## Re-seeding

All seed scripts use **upsert** operations, meaning:

- If data already exists, it will be **updated**
- If data doesn't exist, it will be **inserted**

This makes it safe to run the seed scripts multiple times.

## Customization

You can customize the seed data by editing the respective files:

- `seed_permissions.py` - Modify permissions and roles
- `seed_leave_types.py` - Adjust leave types and allowances
- `seed_admin.py` - Change admin credentials (before first run)
- `seed_holidays.py` - Update holidays for your region/year

## Troubleshooting

### Issue: "No such container"

**Solution**: Make sure Docker containers are running:

```bash
docker-compose up -d
```

### Issue: Seed script fails with connection error

**Solution**: Ensure MongoDB container is healthy:

```bash
docker-compose ps
docker logs fairpay_hrm_db
```

### Issue: Need to reset and re-seed

**Solution**:

```bash
# Reset database
docker-compose down -v
docker-compose up -d

# Wait a few seconds for MongoDB to start, then seed
docker exec fairpay_hrm_backend python seed_all.py
```

## Notes

- Seed scripts automatically detect if running inside Docker and adjust connection strings accordingly
- The admin user's password is hashed using bcrypt before storage
- All timestamps use UTC
- Permissions are linked to roles by their MongoDB ObjectIDs
