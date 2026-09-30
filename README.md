# Pet Vaccination System

A full-stack application for managing pet vaccination records and coordinating
pet owners, doctors, and administrators.

## Overview

- **Frontend:** React 19, React Router, Bootstrap, and Axios.
- **Backend:** Django 6, Django REST Framework, and JWT authentication.
- **Database:** MySQL 8. MySQL is required; SQLite is not supported.
- **Containers:** Docker images for the Django API and React/Nginx web app.
- **Deployment:** Kubernetes manifests for MySQL, the API, and the web app.

The application includes account registration and login, role-specific
owner/doctor/admin workflows, pet profiles and vaccination summaries, doctor
approval/verification, password reset and email OTP flows, and vaccination
reminder functionality. See [docs/AUTH_AND_DATABASE_GUIDE.md](docs/AUTH_AND_DATABASE_GUIDE.md)
for the authentication and database verification guide.

## Repository layout

| Path | Description |
| --- | --- |
| `backend/` | Django project, API apps, database migrations, tests, and Dockerfile |
| `frontend/` | React application, Nginx configuration, and Dockerfile |
| `docs/` | Additional project and verification documentation |
| `dev-local.js` | Root development launcher for Django and React |
| `*-deployment.yaml`, `*-service.yaml` | Kubernetes workload and service manifests |
| `mysql-pvc.yaml` | Persistent volume claim for MySQL data |

## Requirements

For local development:

- Python 3.12
- Node.js 20 or later and npm (the frontend Docker build uses Node 20)
- MySQL 8

For container or cluster deployment, install Docker and a Kubernetes cluster
such as Minikube or another cluster with a default StorageClass.

## Local development

### 1. Configure MySQL

Start MySQL and create a database and a non-root user. For example, connect to
your MySQL server as an administrator and run the following SQL, replacing the
password with a strong local password:

```sql
CREATE DATABASE pet_vaccination_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'pet_app'@'%' IDENTIFIED BY 'replace-with-a-strong-password';
GRANT ALL PRIVILEGES ON pet_vaccination_db.* TO 'pet_app'@'%';
FLUSH PRIVILEGES;
```

`%` allows connections from other containers; for a local-only MySQL setup,
restrict the account host to your connection requirements.

### 2. Configure the backend

From the repository root, create and activate a virtual environment, install
the backend requirements, and copy the environment template:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
cp backend/.env.example backend/.env
```

On Windows PowerShell, create the environment with `py -3.12 -m venv .venv`
and activate it with `.venv\\Scripts\\Activate.ps1`.

Edit `backend/.env` and set at least `DB_NAME`, `DB_USER`, and `DB_PASSWORD` to
the MySQL database and account you created. Keep `DB_HOST=127.0.0.1` and
`DB_PORT=3306` when MySQL is running on the same machine. A unique local Django
`SECRET_KEY` is generated and saved automatically on the first backend start
when the template placeholder is unchanged.

Email settings in `backend/.env` are needed for email OTP and email delivery.
For Gmail, use a Google App Password, not your regular Google password. Do not
commit `backend/.env` or put real credentials in the repository.

### 3. Install the frontend and start the app

From the repository root:

```bash
npm --prefix frontend ci
npm run dev
```

The root `npm run dev` launcher checks the MySQL connection, applies Django
migrations, starts the backend, waits for its database health check, and then
starts the React development server. Stop both processes with **Ctrl+C**.

| Service | Local URL |
| --- | --- |
| React frontend | http://localhost:3000 |
| Django API | http://127.0.0.1:8000 |
| Django health check | http://127.0.0.1:8000/health/ |
| Django admin | http://127.0.0.1:8000/admin/ |

The frontend development server proxies API requests to the local Django API.
The launcher does not install MySQL or create the database/user for you; those
must be set up before running it.

### Backend and frontend checks

Run Django tests from the project root after activating the virtual environment:

```bash
cd backend
python manage.py test
```

Create a production frontend build with:

```bash
npm --prefix frontend run build
```

## Docker

Build both images from the repository root:

```bash
docker build -t pet-backend:dev ./backend
docker build -t pet-frontend:dev ./frontend
```

The backend image uses Python 3.12, installs the packages in
`backend/requirements.txt`, waits for MySQL, applies migrations, checks the
database, and starts Django on port 8000. The frontend image builds React and
serves it with Nginx on port 80.

There is no Docker Compose file in this repository. The Nginx configuration
proxies `/api/` to the hostname `pet-backend-service`, which is the Kubernetes
backend Service name. You can run all three containers on one Docker network as
follows. First, create two **untracked files outside the repository**: a MySQL
environment file containing `MYSQL_ROOT_PASSWORD`, `MYSQL_DATABASE`,
`MYSQL_USER`, and `MYSQL_PASSWORD`; and the backend's `backend/.env` file with
the database values, a strong `SECRET_KEY`, and any email settings. For this
Docker setup, set `DB_HOST=mysql` in `backend/.env` (use `127.0.0.1` for local
development instead).

```bash
docker network create pet-vaccination
docker volume create pet-mysql-data
docker run -d --name pet-mysql --network pet-vaccination --network-alias mysql --env-file /secure/path/mysql.env -v pet-mysql-data:/var/lib/mysql mysql:8.0
docker run -d --name pet-backend --network pet-vaccination --network-alias pet-backend-service --env-file backend/.env -p 8000:8000 pet-backend:dev
docker run -d --name pet-frontend --network pet-vaccination -p 3000:80 pet-frontend:dev
```

Replace `/secure/path/mysql.env` with the path to your protected MySQL
environment file. Open http://localhost:3000. The backend container waits for
MySQL and runs migrations when it starts. Keep passwords out of shell history;
use protected, untracked files or a container secret manager.

## Kubernetes deployment

The manifests in the repository deploy MySQL with persistent storage, the
Django API, and the React/Nginx frontend. These steps assume `kubectl` is
configured for your target cluster and that the cluster has a StorageClass
capable of satisfying the 1 GiB `ReadWriteOnce` claim in `mysql-pvc.yaml`.

### 1. Build images for the cluster

For Minikube, build the images into its image store so the deployments can use
them without pulling from a registry:

```bash
minikube image build -t pet-backend:dev ./backend
minikube image build -t pet-frontend:dev ./frontend
```

For another cluster, push both images to a registry accessible to the cluster
and update the image names in the deployment manifests to those registry
references. The frontend deployment uses `imagePullPolicy: Never`, so it
requires the image to already exist on the cluster node unless that setting is
changed.

### 2. Create Kubernetes Secrets

The local `mysql-secret.yaml` is ignored by Git and must not be used as-is: it
contains example credentials, and the backend deployment also requires a
`DJANGO_SECRET_KEY` value. Create a private environment file **outside
the repository** with the following keys and strong, unique values:

```dotenv
MYSQL_ROOT_PASSWORD=replace-with-a-strong-root-password
MYSQL_DATABASE=pet_vaccination_db
MYSQL_USER=pet_app
MYSQL_PASSWORD=replace-with-a-strong-database-password
DJANGO_SECRET_KEY=replace-with-a-long-random-django-secret
```

Then create/update the cluster Secret from that file:

```bash
kubectl create secret generic mysql-secret --from-env-file=/secure/path/mysql-secret.env --dry-run=client -o yaml | kubectl apply -f -
```

Replace `/secure/path/mysql-secret.env` with the actual protected file path.
The environment file should not be committed or stored in the project. If you
configure email delivery in Kubernetes, create an `email-secret` with the email
settings referenced by `backend-deployment.yaml`; those values are optional in
the current manifest.

### 3. Apply the manifests

```bash
kubectl apply -f mysql-pvc.yaml
kubectl apply -f mysql-service.yaml -f mysql-deployment.yaml
kubectl apply -f backend-service.yaml -f backend-deployment.yaml
kubectl apply -f frontend-service.yaml -f frontend-deployment.yaml
```

Check that pods, services, and storage become ready:

```bash
kubectl get pods,services,pvc
```

Open the frontend locally using port forwarding:

```bash
kubectl port-forward service/pet-frontend-service 8080:80
```

Then visit http://localhost:8080. Leave the port-forward process running while
using the site. MySQL is exposed inside the cluster only; the backend Service
also defines NodePort `30817`.

### Deployment considerations

- Use a secrets manager or Kubernetes Secrets for all real passwords and the
  Django secret key. Never commit populated Secret manifests.
- The Kubernetes backend deployment sets `DEBUG=False`. Uploaded media is not
  backed by a persistent volume in the current manifests; configure persistent
  media storage and serving before relying on uploaded photos in a deployment.
- The backend container currently starts Django's development server. For a
  production deployment, use a production-grade WSGI/ASGI server and configure
  `ALLOWED_HOSTS`, HTTPS, persistent media, and email delivery for your domain.
- Vaccination reminder code and a cron configuration are present; arrange and
  verify a scheduler in your deployment before relying on automatic reminder
  delivery.

## Configuration reference

Backend environment values are documented by `backend/.env.example`:

| Variable | Purpose |
| --- | --- |
| `DB_ENGINE` | Must be `mysql` |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD` | MySQL database and credentials |
| `DB_HOST`, `DB_PORT` | MySQL host and port; local defaults are `127.0.0.1` and `3306` |
| `SECRET_KEY` | Django signing key; required for deployment |
| `DEBUG` | Django debug setting; use `False` for deployments |
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS` | SMTP server configuration |
| `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL` | SMTP account and sender |

## Keeping data and credentials safe

Commit source code, migrations, tests, dependency manifests, Dockerfiles,
Kubernetes manifests that reference Secrets, and documentation. Do not commit
real `.env` files, Kubernetes Secret values, API/email/database credentials,
database files or dumps, uploaded media, or private user/pet information.
`.gitignore` excludes common local secrets and generated files, but always
review the staged file list before pushing. Rotate any credential that has
ever been committed.
