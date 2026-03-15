#!/bin/bash
# ══════════════════════════════════════════════════════════════════════════════
# deploy.sh — Full production deployment script
#
# Usage (first time):  bash deploy.sh --init
# Usage (update):      bash deploy.sh
# ══════════════════════════════════════════════════════════════════════════════
set -euo pipefail

COMPOSE="docker compose -f docker-compose.prod.yml"

# ── Colour helpers ────────────────────────────────────────────────────────────
GREEN="\033[0;32m"; YELLOW="\033[1;33m"; RED="\033[0;31m"; NC="\033[0m"
info()    { echo -e "${GREEN}[deploy]${NC} $*"; }
warn()    { echo -e "${YELLOW}[warn]${NC}  $*"; }
die()     { echo -e "${RED}[error]${NC} $*"; exit 1; }

# ── Preflight checks ──────────────────────────────────────────────────────────
[[ -f .env ]] || die ".env not found — copy .env.example and fill in your values"
command -v docker &>/dev/null || die "Docker not installed"
docker compose version &>/dev/null || die "Docker Compose plugin not installed"

source .env
[[ "${FRONTEND_URL:-}" == https://* ]] || warn "FRONTEND_URL doesn't start with https:// — participants need HTTPS"

# ── First-time init: install Docker, get SSL cert ────────────────────────────
if [[ "${1:-}" == "--init" ]]; then
    DOMAIN="${FRONTEND_URL#https://}"
    info "Running first-time init for domain: $DOMAIN"

    info "Installing certbot..."
    apt-get update -q && apt-get install -y -q certbot

    info "Obtaining SSL certificate (port 80 must be free)..."
    certbot certonly --standalone \
        -d "$DOMAIN" \
        --non-interactive \
        --agree-tos \
        -m "${SMTP_USER:-admin@example.com}"

    # Replace the ${DOMAIN} placeholder in nginx config
    sed -i "s/\${DOMAIN}/$DOMAIN/g" nginx/default.conf
    info "nginx config updated for $DOMAIN"
fi

# ── Build & start ─────────────────────────────────────────────────────────────
info "Building images..."
$COMPOSE build --pull

info "Starting services..."
$COMPOSE up -d

info "Waiting for backend to start (entrypoint runs migrations automatically)..."
for i in $(seq 1 30); do
    if $COMPOSE logs backend 2>/dev/null | grep -q "Application startup complete\|Uvicorn running\|Starting application"; then
        info "Backend is ready."
        break
    fi
    echo "  waiting for backend... ($i/30)"
    sleep 5
done

# ── First-time DB seed ────────────────────────────────────────────────────────
if [[ "${1:-}" == "--init" ]]; then
    info "Seeding database..."
    $COMPOSE exec -T backend python -m app.db.seed_data
    $COMPOSE exec -T backend python -m app.db.seed_scenarios
    info "Database seeded."
fi

# ── Health check ──────────────────────────────────────────────────────────────
info "Checking service health..."
$COMPOSE ps

DOMAIN="${FRONTEND_URL:-http://localhost}"
echo ""
info "Deployment complete!"
info "Site:       $DOMAIN"
info "Admin:      $DOMAIN/admin"
info "API docs:   $DOMAIN/api/v1/docs"
echo ""
info "Useful commands:"
echo "  $COMPOSE logs -f backend        # live backend logs"
echo "  $COMPOSE logs -f celery_worker  # live worker logs"
echo "  $COMPOSE ps                     # service status"
echo "  $COMPOSE restart backend        # restart after code change"
