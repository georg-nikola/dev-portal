#!/bin/bash
# Creates required Kubernetes secrets for the dev-portal namespace.
#
# Usage:
#   POSTGRES_PASSWORD=<password> ./scripts/create-k8s-secrets.sh            # Apply plain secrets
#   POSTGRES_PASSWORD=<password> ./scripts/create-k8s-secrets.sh --sealed   # Generate SealedSecret YAMLs
#
# Sealed Secrets migration path:
#   1. Deploy sealed-secrets controller to the cluster (see talos-configs ArgoCD app)
#   2. Install kubeseal: brew install kubeseal
#   3. Run this script with --sealed to generate SealedSecret YAML files
#   4. Commit the SealedSecret files to git (they are encrypted, safe to store)
#   5. Apply them: kubectl apply -f <sealed-secret-file>.yaml
#   6. The controller decrypts them into regular Secrets in-cluster

set -euo pipefail

: "${POSTGRES_PASSWORD:?Environment variable POSTGRES_PASSWORD must be set}"

SEALED=false
SEALED_OUTPUT_DIR="./sealed-secrets"

if [ "${1:-}" = "--sealed" ]; then
    SEALED=true
    echo "Mode: Sealed Secrets (will generate SealedSecret YAML files)"
    echo "Prerequisites: kubeseal CLI installed, sealed-secrets controller running in cluster"
    if ! command -v kubeseal &> /dev/null; then
        echo "ERROR: kubeseal not found. Install with: brew install kubeseal"
        exit 1
    fi
    mkdir -p "$SEALED_OUTPUT_DIR"
    echo ""
fi

# Helper: either apply secret directly or seal it
apply_or_seal() {
  local secret_name="$1"
  local secret_yaml

  secret_yaml=$(cat)

  if [ "$SEALED" = true ]; then
    local output_file="${SEALED_OUTPUT_DIR}/${secret_name}.yaml"
    echo "$secret_yaml" | kubeseal --format yaml > "$output_file"
    echo "Sealed secret written to: $output_file (safe to commit to git)"
  else
    echo "$secret_yaml" | kubectl apply -f -
  fi
}

echo "Creating namespace dev-portal (idempotent)..."
kubectl create namespace dev-portal --dry-run=client -o yaml | kubectl apply -f -

echo "Creating secret: postgresql-credentials..."
kubectl create secret generic postgresql-credentials \
  --namespace=dev-portal \
  --from-literal=POSTGRES_DB=devportal \
  --from-literal=POSTGRES_USER=devportal \
  --from-literal=POSTGRES_PASSWORD="${POSTGRES_PASSWORD}" \
  --dry-run=client -o yaml | apply_or_seal "postgresql-credentials"

echo ""
echo "Creating secret: postgresql-tls (TLS certificates for PostgreSQL SSL)..."
CERT_DIR="./pg-certs"
if [ ! -f "$CERT_DIR/server.crt" ]; then
  echo "Generating PostgreSQL TLS certificates..."
  ./scripts/generate-pg-certs.sh "$CERT_DIR"
fi
kubectl create secret generic postgresql-tls \
  --namespace=dev-portal \
  --from-file=server.crt="$CERT_DIR/server.crt" \
  --from-file=server.key="$CERT_DIR/server.key" \
  --from-file=ca.crt="$CERT_DIR/ca.crt" \
  --dry-run=client -o yaml | apply_or_seal "postgresql-tls"

echo ""
if [ "$SEALED" = true ]; then
  echo "SealedSecret files generated in: $SEALED_OUTPUT_DIR/"
  echo "These files are safe to commit to git."
  echo ""
  echo "To apply them:"
  echo "  kubectl apply -f $SEALED_OUTPUT_DIR/"
else
  echo "Done. Secrets created in namespace dev-portal."
fi
