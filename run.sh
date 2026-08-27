#!/bin/bash
# Town Market - Run Backend and Frontend Together
# Supports three modes: development, production, and docker
#
# Usage: bash run.sh [mode]
#   bash run.sh dev    - Development mode (local development, SQLite)
#   bash run.sh prod   - Production mode (PostgreSQL)
#   bash run.sh docker - Docker mode (Docker Compose with all services)
#
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if we are in the town_market directory
if [ ! -f "manage.py" ]; then
    print_error "This script must be run from the town_market directory"
    print_info "Current directory: $(pwd)"
    exit 1
fi

# ============================================================================
# Mode Selection
# ============================================================================

if [ -z "$1" ]; then
    echo ""
    echo "========================================="
    echo "  Town Market - Backend & Frontend"
    echo "========================================="
    echo ""
    print_info "Usage: bash run.sh [mode]"
    echo ""
    print_info "  Modes:"
    echo "    dev         - Local dev (SQLite, no Docker)"
    echo "    prod        - Local prod (PostgreSQL, no Docker)"
    echo "    docker-dev  - Docker DEV (Django direct on :8000, no Nginx)"
    echo "    docker-prod - Docker PROD (Gunicorn + Nginx on :8082)"
    echo ""
    print_info "Examples:"
    echo "  bash run.sh dev          # Local development"
    echo "  sudo bash run.sh docker-dev   # Docker dev (no Nginx)"
    echo "  sudo bash run.sh docker-prod  # Docker prod (with Nginx)"
    echo ""
    exit 1
fi

MODE="$1"

# ============================================================================
# Development Mode
# ============================================================================
if [ "$MODE" = "dev" ] || [ "$MODE" = "development" ]; then
    echo ""
    echo "========================================="
    echo "  Town Market - Development Mode"
    echo "========================================="
    echo ""
    print_info "Starting Town Market in DEVELOPMENT mode..."
    echo ""
    print_info "Backend:  Django with SQLite (port 8000)"
    print_info "Frontend: React + Vite (port 3000)"
    echo ""
    print_info "Using SQLite for database (no PostgreSQL required)"
    echo ""
    print_info "Making sure ports 8000 and 3000 are available..."
    echo ""

    # Check if ports are available
    check_port() {
        local port=$1
        local service=$2
        if lsof -i :$port > /dev/null 2>&1; then
            print_warning "$service is already running on port $port"
            return 1
        fi
        return 0
    }

    check_port 8000 "Django" || exit 1
    check_port 3000 "Frontend" || exit 1

    print_success "Both ports are available!"
    echo ""

    # Start React Frontend in background
    print_info "Starting React Frontend (port 3000)..."
    cd /home/salahuddin/Town/frontend
    npm run dev &
    FRONTEND_PID=$!

    # Wait a moment for frontend to start
    sleep 3

    # Start Django Backend in background
    print_info "Starting Django Backend (port 8000)..."
    cd /home/salahuddin/Town/town_market
    print_info "Using SQLite database for development mode..."
    # Use SQLite for development mode by setting DATABASE_URL env var
    DATABASE_URL=sqlite:///db.sqlite3 python3 manage.py runserver 0.0.0.0:8000 &
    BACKEND_PID=$!

    # Restore original .env if we swapped it
    if [ -f .env.bak ]; then
        cp .env.bak .env
        rm .env.bak
    fi

    echo ""
    echo "========================================="
    echo "  Services Running"
    echo "========================================="
    echo ""
    echo "  Backend:  http://127.0.0.1:8000 (PID: $BACKEND_PID)"
    echo "  Frontend: http://127.0.0.1:3000 (PID: $FRONTEND_PID)"
    echo ""
    echo "  Press Ctrl+C to stop both services"
    echo ""

    # Wait for Ctrl+C
    trap 'echo ""; print_info "Stopping services..."; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; print_success "Both services stopped"; exit 0' INT

    # Wait for background processes
    wait
fi

# ============================================================================
# Production Mode
# ============================================================================
if [ "$MODE" = "prod" ] || [ "$MODE" = "production" ]; then
    echo ""
    echo "========================================="
    echo "  Town Market - Production Mode"
    echo "========================================="
    echo ""
    print_info "Starting Town Market in PRODUCTION mode..."
    echo ""
    print_info "Backend:  Django with PostgreSQL (port 8000)"
    print_info "Frontend: React + Vite (port 3000)"
    echo ""
    print_info "Using PostgreSQL database (ensure PostgreSQL is running)"
    echo ""
    print_info "Making sure ports 8000 and 3000 are available..."
    echo ""

    # Check if ports are available
    check_port() {
        local port=$1
        local service=$2
        if lsof -i :$port > /dev/null 2>&1; then
            print_warning "$service is already running on port $port"
            return 1
        fi
        return 0
    }

    check_port 8000 "Django" || exit 1
    check_port 3000 "Frontend" || exit 1

    print_success "Both ports are available!"
    echo ""

    # Start React Frontend in background
    print_info "Starting React Frontend (port 3000)..."
    cd /home/salahuddin/Town/frontend
    npm run dev &
    FRONTEND_PID=$!

    # Wait a moment for frontend to start
    sleep 3

    # Start Django Backend in background
    print_info "Starting Django Backend (port 8000)..."
    cd /home/salahuddin/Town/town_market
    print_info "Using PostgreSQL database..."
    python3 manage.py runserver 0.0.0.0:8000 &
    BACKEND_PID=$!

    echo ""
    echo "========================================="
    echo "  Services Running"
    echo "========================================="
    echo ""
    echo "  Backend:  http://127.0.0.1:8000 (PID: $BACKEND_PID)"
    echo "  Frontend: http://127.0.0.1:3000 (PID: $FRONTEND_PID)"
    echo ""
    echo "  Press Ctrl+C to stop both services"
    echo ""

    # Wait for Ctrl+C
    trap 'echo ""; print_info "Stopping services..."; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; print_success "Both services stopped"; exit 0' INT

    # Wait for background processes
    wait
fi

# ============================================================================
# Docker DEV Mode  (no Nginx — Django direct on port 8000)
# ============================================================================
if [ "$MODE" = "docker-dev" ]; then
    echo ""
    echo "========================================="
    echo "  Town Market - Docker DEV Mode"
    echo "========================================="
    echo ""
    print_info "Django runs directly on port 8000 (no Nginx)"
    print_info "React frontend runs on port 3000"
    print_info "Live code reload via volume mounts"
    print_info "Services: React + Django + PostgreSQL + Redis + Celery"
    echo ""

    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed or not in PATH"
        exit 1
    fi

    if docker compose version &> /dev/null 2>&1; then
        COMPOSE_CMD="docker compose"
    elif command -v docker-compose &> /dev/null; then
        print_warning "Falling back to docker-compose v1"
        COMPOSE_CMD="docker-compose"
    else
        print_error "Docker Compose not found"
        exit 1
    fi

    if [ ! -f ".env" ]; then
        print_error ".env file not found!"
        exit 1
    fi

    print_info "Starting Docker DEV services..."
    $COMPOSE_CMD -f docker-compose.dev.yml up --build -d

    sleep 5
    echo ""
    echo "Checking service status..."
    $COMPOSE_CMD -f docker-compose.dev.yml ps

    echo ""
    echo "========================================="
    echo "  Docker DEV Services Running"
    echo "========================================="
    echo ""
    echo "  Django API (direct):  http://localhost:8000"
    echo "  React Frontend:       http://localhost:3000"
    echo "  PostgreSQL:           localhost:5431"
    echo "  Redis:                localhost:6380"
    echo ""
    echo "  Press Ctrl+C to stop and remove containers"
    echo ""

    trap 'echo ""; print_info "Stopping DEV containers..."; $COMPOSE_CMD -f docker-compose.dev.yml down; print_success "Containers stopped"' INT

    $COMPOSE_CMD -f docker-compose.dev.yml logs -f
fi

# ============================================================================
# Docker PROD Mode  (Nginx on 8082 → Gunicorn → Django)
# ============================================================================
if [ "$MODE" = "docker-prod" ]; then
    echo ""
    echo "========================================="
    echo "  Town Market - Docker PROD Mode"
    echo "========================================="
    echo ""
    print_info "Gunicorn serves Django (3 workers)"
    print_info "Nginx reverse proxy on port 8082"
    print_info "Services: Nginx + Django + PostgreSQL + Redis + Celery"
    echo ""

    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed or not in PATH"
        exit 1
    fi

    if docker compose version &> /dev/null 2>&1; then
        COMPOSE_CMD="docker compose"
    elif command -v docker-compose &> /dev/null; then
        print_warning "Falling back to docker-compose v1"
        COMPOSE_CMD="docker-compose"
    else
        print_error "Docker Compose not found"
        exit 1
    fi

    if [ ! -f ".env" ]; then
        print_error ".env file not found!"
        exit 1
    fi

    print_info "Starting Docker PROD services..."
    $COMPOSE_CMD -f docker-compose.prod.yml up --build -d

    sleep 8
    echo ""
    echo "Checking service status..."
    $COMPOSE_CMD -f docker-compose.prod.yml ps

    echo ""
    echo "========================================="
    echo "  Docker PROD Services Running"
    echo "========================================="
    echo ""
    echo "  Web API via Nginx:    http://localhost:8082"
    echo "  PostgreSQL:           localhost:5431"
    echo "  Redis:                localhost:6380"
    echo ""
    echo "  Press Ctrl+C to stop and remove containers"
    echo ""

    trap 'echo ""; print_info "Stopping PROD containers..."; $COMPOSE_CMD -f docker-compose.prod.yml down; print_success "Containers stopped"' INT

    $COMPOSE_CMD -f docker-compose.prod.yml logs -f
fi

# ============================================================================
# Invalid Mode
# ============================================================================
VALID_MODES="dev development prod production docker-dev docker-prod"
if ! echo "$VALID_MODES" | grep -qw "$MODE"; then
    echo ""
    print_error "Invalid mode: '$MODE'"
    echo ""
    print_info "Valid modes:"
    echo "  dev / development   — Local dev (SQLite, no Docker)"
    echo "  prod / production   — Local prod (PostgreSQL, no Docker)"
    echo "  docker-dev          — Docker DEV (Django direct, no Nginx)"
    echo "  docker-prod         — Docker PROD (Gunicorn + Nginx)"
    echo ""
    exit 1
fi