# BIC-CCD Deployment Guide

## Environment Strategy

| Environment | Database | Auth | Evidence | Email | Config File |
|-------------|----------|------|----------|-------|-------------|
| **DEV** | SQLite | JWT (any password) | Local filesystem | Disabled (logs only) | `config/.env.development` |
| **UAT** | Oracle 19c UAT | JWT + LDAP | S3 UAT bucket | UAT SMTP relay | `config/.env.uat` |
| **PROD** | Oracle 19c RAC | JWT + SSO/LDAP | S3 prod bucket | Prod SMTP relay | `config/.env.production` |

## DEV Setup (Local)

```bash
# 1. Backend
cd backend
cp config/.env.development .env
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
# Auto-creates SQLite DB + seeds 24 KRIs, 7 users, 6 months data

# 2. Frontend
cd frontend
cp .env.development .env
npm install
npm run dev
# Opens at http://localhost:5173, proxies /api to :8000
```

## UAT Deployment (Docker)

```bash
# 1. Set secrets (inject via CI/CD or vault)
export DB_PASSWORD=<oracle-uat-password>
export JWT_SECRET=<strong-random-secret>
export S3_ACCESS_KEY=<s3-uat-key>
export S3_SECRET_KEY=<s3-uat-secret>

# 2. Copy UAT config
cd backend && cp config/.env.uat .env
cd ../frontend && cp .env.uat .env

# 3. Build and deploy
docker-compose -f docker-compose.yml -f docker-compose.uat.yml up --build -d

# 4. Run Oracle schema
sqlplus bic_ccd_uat/$DB_PASSWORD@//oracle-uat:1521/BICCCD_UAT < database/schema.sql

# 5. Verify
curl https://bic-ccd-uat.internal.company.com/health
```

## PROD Deployment (Kubernetes/OpenShift)

```bash
# 1. Create namespace
kubectl create namespace bic-ccd-prod

# 2. Create secrets from vault
kubectl create secret generic bic-ccd-secrets \
  --from-literal=DB_PASSWORD=$DB_PASSWORD \
  --from-literal=JWT_SECRET=$JWT_SECRET \
  --from-literal=S3_ACCESS_KEY=$S3_ACCESS_KEY \
  --from-literal=S3_SECRET_KEY=$S3_SECRET_KEY \
  --from-literal=SMTP_PASSWORD=$SMTP_PASSWORD \
  -n bic-ccd-prod

# 3. Apply manifests
kubectl apply -f k8s/prod/ -n bic-ccd-prod

# 4. Run Oracle schema (one-time)
sqlplus bic_ccd_prod/$DB_PASSWORD@//oracle-prod-scan:1521/BICCCD_PROD < database/schema.sql

# 5. Verify
kubectl get pods -n bic-ccd-prod
curl https://bic-ccd.company.com/health
```

## Database Migration (Alembic)

```bash
cd backend

# Generate migration after model changes
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback one step
alembic downgrade -1
```

## Health Checks

| Endpoint | Purpose | Expected |
|----------|---------|----------|
| `GET /health` | Application health | `{"status": "healthy"}` |
| `GET /api/health` | API + DB connectivity | `{"status": "healthy", "database": "connected"}` |

## Production Checklist

- [ ] Oracle 19c schema created with `database/schema.sql`
- [ ] S3 bucket created with appropriate IAM policy
- [ ] JWT_SECRET is cryptographically strong (min 32 chars)
- [ ] SECRET_KEY is unique per environment
- [ ] CORS_ORIGINS restricted to production frontend URL only
- [ ] SMTP relay configured and tested
- [ ] HTTPS/TLS configured via nginx or ingress
- [ ] Log aggregation configured (ELK/Splunk) for JSON logs
- [ ] Database backups scheduled
- [ ] Monitoring alerts set for health endpoint
- [ ] SSO/LDAP integration replacing demo auth
- [ ] Rate limiting enabled
- [ ] Connection pooling tuned for expected load
