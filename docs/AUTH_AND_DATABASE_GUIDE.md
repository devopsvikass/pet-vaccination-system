# Authentication and Database Guide

This document explains how login works for `owner`, `doctor`, and `admin`, and how to verify whether data is being stored in MySQL correctly.

## 1. Login Model

Backend login endpoint:
- `POST /api/accounts/login/`

Accepted login payload:
- `username` + `password`
- or `email` + `password`
- optional `role` (`owner`, `doctor`, `admin`) for role-specific login validation

Successful response includes:
- `access` (JWT token)
- `refresh` (JWT token)
- `role`
- `user_id`
- `doctor_status`

## 2. Role Rules

- `owner`
  - Can add/manage own pets.
  - Cannot access admin-only endpoints.
- `doctor`
  - Can log in as doctor.
  - Must be approved/verified to access doctor-protected pet endpoints.
- `admin`
  - Can access user management endpoints like `/api/accounts/all/`.
  - Can create other admins via `/api/accounts/admins/create/`.

## 3. MySQL Configuration

In `backend/.env`:

```env
DB_ENGINE=mysql
DB_NAME=pet_vaccination_db
DB_USER=your_mysql_user
DB_PASSWORD=your_mysql_password
DB_HOST=127.0.0.1
DB_PORT=3306
```

Keep these real credentials in the ignored `backend/.env` file. For Gmail OTP
delivery, configure `EMAIL_HOST_USER` and `EMAIL_HOST_PASSWORD` there using a
Google App Password, not the account password. Never commit `.env` files or
paste credentials into source code. For GitHub Actions, store deployment
credentials as repository/environment secrets and pass them to the deployment
as environment variables.

## 4. Verify Data Is in MySQL

Run from project root:

```bash
./venv/bin/python backend/manage.py shell -c "from django.contrib.auth import get_user_model; from pets.models import Pet, DoctorSummary; U=get_user_model(); print('users', U.objects.count()); print('pets', Pet.objects.count()); print('summaries', DoctorSummary.objects.count()); print('roles', {r: U.objects.filter(role=r).count() for r in ['owner','doctor','admin']})"
```

If this command succeeds and prints counts, Django is reading MySQL correctly.

## 5. Common Login Failure Causes

`401 Unauthorized` on `/api/accounts/login/` usually means:
- wrong password
- user does not exist in current DB
- user is inactive

`403 Forbidden` usually means:
- role mismatch (example: trying to log in with `role=owner` for an `admin` account)

## 6. Admin Login Checklist

1. Confirm MySQL is selected (`DB_ENGINE=mysql`).
2. Confirm at least one admin exists in MySQL.
3. Confirm admin flags:
   - `role='admin'`
   - `is_active=True`
   - `is_staff=True`
   - `is_superuser=True`
4. Login with:
   - `username + password` (or `email + password`)
   - role `admin` for admin portal flows.

## 7. Create Admin from Shell (If Needed)

```bash
./venv/bin/python backend/manage.py shell -c "from django.contrib.auth import get_user_model; U=get_user_model(); U.objects.create_user(username='admin2', email='admin2@example.com', password='StrongPass@123', phone='9999999998', role='admin', is_staff=True, is_superuser=True, is_active=True, doctor_status='approved', doctor_approved=True, doctor_verified=True); print('admin created')"
```

## 8. Security Note

Local development generates a unique `SECRET_KEY` in the ignored
`backend/.env` file if one is missing. For deployment, set `DEBUG=False` and
provide a unique `SECRET_KEY` through your deployment secret manager. The
Kubernetes backend manifest expects it under the `DJANGO_SECRET_KEY` key in the
`mysql-secret` Secret. Do not put email passwords, database passwords, or the
Django signing key in tracked source files.
