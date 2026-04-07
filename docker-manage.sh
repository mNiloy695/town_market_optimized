#!/bin/bash

# Town Market Docker Management Script

set -e

PROJECT_NAME="town_market"

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

# Check if .env file exists
check_env_file() {
    if [ ! -f ".env" ]; then
        print_error ".env file not found!"
        print_info "Copy .env.example to .env and configure your environment variables"
        exit 1
    fi
}

# Build and start services
start() {
    print_info "Starting Town Market services..."
    check_env_file
    docker-compose up --build -d
    print_success "Services started successfully!"
    print_info "Django app: http://localhost:8000"
    print_info "PostgreSQL: localhost:5432"
    print_info "Redis: localhost:6379"
}

# Stop services
stop() {
    print_info "Stopping Town Market services..."
    docker-compose down
    print_success "Services stopped successfully!"
}

# View logs
logs() {
    if [ -z "$2" ]; then
        docker-compose logs -f
    else
        docker-compose logs -f "$2"
    fi
}

# Run Django management commands
manage() {
    check_env_file
    if [ -z "$2" ]; then
        print_error "Please specify a management command"
        exit 1
    fi
    print_info "Running: python manage.py $@"
    docker-compose exec web python manage.py "${@:2}"
}

# Run database migrations
migrate() {
    print_info "Running database migrations..."
    manage migrate
    print_success "Migrations completed!"
}

# Create superuser
createsuperuser() {
    print_info "Creating Django superuser..."
    manage createsuperuser
}

# Run tests
test() {
    print_info "Running Django tests..."
    manage test
}

# Clean up
clean() {
    print_warning "This will remove all containers, volumes, and images"
    read -p "Are you sure? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_info "Cleaning up Docker resources..."
        docker-compose down -v --rmi all
        print_success "Cleanup completed!"
    fi
}

# Show status
status() {
    print_info "Service Status:"
    docker-compose ps
}

# Show help
help() {
    echo "Town Market Docker Management Script"
    echo ""
    echo "Usage: $0 [command] [options]"
    echo ""
    echo "Commands:"
    echo "  start              Build and start all services"
    echo "  stop               Stop all services"
    echo "  logs [service]     View logs (optionally for specific service)"
    echo "  manage <command>   Run Django management command"
    echo "  migrate            Run database migrations"
    echo "  createsuperuser    Create Django superuser"
    echo "  test               Run Django tests"
    echo "  status             Show service status"
    echo "  clean              Remove all containers, volumes, and images"
    echo "  help               Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 start"
    echo "  $0 logs web"
    echo "  $0 manage makemigrations"
    echo "  $0 manage shell"
}

# Main script logic
case "$1" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    logs)
        logs "$@"
        ;;
    manage)
        manage "$@"
        ;;
    migrate)
        migrate
        ;;
    createsuperuser)
        createsuperuser
        ;;
    test)
        test
        ;;
    status)
        status
        ;;
    clean)
        clean
        ;;
    help|--help|-h)
        help
        ;;
    *)
        print_error "Unknown command: $1"
        echo ""
        help
        exit 1
        ;;
esac