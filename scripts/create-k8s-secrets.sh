#!/bin/bash
# Creates required Kubernetes secrets for the dev-portal namespace.
# Usage: POSTGRES_PASSWORD=<password> ./scripts/create-k8s-secrets.sh
set -euo pipefail

: "${POSTGRES_PASSWORD:?Environment variable POSTGRES_PASSWORD must be set}"

echo "Creating namespace dev-portal (idempotent)..."
kubectl create namespace dev-portal --dry-run=client -o yaml | kubectl apply -f -

echo "Creating secret: postgresql-credentials..."
kubectl create secret generic postgresql-credentials \
  --namespace=dev-portal \
  --from-literal=POSTGRES_DB=devportal \
  --from-literal=POSTGRES_USER=devportal \
  --from-literal=POSTGRES_PASSWORD="${POSTGRES_PASSWORD}" \
  --dry-run=client -o yaml | kubectl apply -f -

echo "Done. Secrets created in namespace dev-portal."
