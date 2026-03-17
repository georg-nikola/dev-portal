# Dev Portal

Internal developer portal — a mini Backstage clone for cataloguing microservices.

Tracks service metadata, health status, links, team ownership, and tags. Includes a background health checker that periodically pings registered `status_url` endpoints and updates service status automatically.

**Domain:** [dev-portal.georg-nikola.com](https://dev-portal.georg-nikola.com)

---

## Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Static HTML/CSS/JS served by nginx |
| Backend | FastAPI (Python 3.12) |
| Database | PostgreSQL 16 |
| Container registry | ghcr.io/georg-nikola |
| Orchestration | Kubernetes (Talos, single node) |
| GitOps | ArgoCD + ArgoCD Image Updater |
| Ingress | Traefik v3 IngressRoute |

---

## Local development

### Prerequisites

- Docker & Docker Compose

### Start everything

```bash
docker compose up --build
```

- Frontend: http://localhost:8080
- API:      http://localhost:8000
- API docs: http://localhost:8000/docs

### Without Docker (backend only)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
DATABASE_URL=postgresql+asyncpg://devportal:devportal@localhost:5432/devportal \
  uvicorn main:app --reload
```

---

## Environment variables

### Backend

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://devportal:devportal@localhost:5432/devportal` | Async PostgreSQL connection string |
| `STATUS_CHECK_INTERVAL` | `60` | Seconds between background health checks |
| `STATUS_CHECK_TIMEOUT` | `10` | HTTP timeout in seconds for health pings |

---

## Kubernetes deployment

### 1. Create namespace and secrets

```bash
POSTGRES_PASSWORD=<strong-password> ./scripts/create-k8s-secrets.sh
```

### 2. Apply ArgoCD applications

```bash
kubectl apply -f k8s/argocd/application-postgresql-dev-portal.yaml
kubectl apply -f k8s/argocd/application-dev-portal-api.yaml
kubectl apply -f k8s/argocd/application-dev-portal.yaml
```

ArgoCD will sync the Helm charts from this repo and deploy to the `dev-portal` namespace.

### 3. Verify

```bash
kubectl get pods -n dev-portal
kubectl get ingressroute -n dev-portal
```

---

## API reference

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/services` | List services (query: `q`, `team`, `status`, `tag`) |
| GET | `/api/services/{id}` | Get one service |
| POST | `/api/services` | Create service |
| PUT | `/api/services/{id}` | Update service |
| DELETE | `/api/services/{id}` | Delete service |
| POST | `/api/services/{id}/check` | Manually trigger health check ping |

Interactive docs: `/docs` (Swagger UI), `/redoc`

---

## CI/CD

- **docker-publish.yml** — builds and pushes images to GHCR on pushes to `main`. Tags: semver, SHA.
- **security-scan.yml** — Gitleaks, Bandit, pip-audit, Trivy IaC, Kubescape.
- **ArgoCD Image Updater** — watches GHCR for new semver tags, patches `values.yaml` automatically.
