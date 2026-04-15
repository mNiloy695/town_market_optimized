# Town Market - Docker Deployment

This application is containerized using Docker and Docker Compose for easy deployment and development.

## Prerequisites

- Docker
- Docker Compose

## Quick Start

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Update the `.env` file with your actual values (especially `SECRET_KEY`)

3. Use the management script for easy operations:
   ```bash
   # Start all services
   ./docker-manage.sh start

   # Run database migrations
   ./docker-manage.sh migrate

   # Create superuser
   ./docker-manage.sh createsuperuser
   ```

## Manual Docker Commands

If you prefer using Docker Compose directly:

1. Build and start all services:
   ```bash
   docker-compose up --build
   ```

2. Run in detached mode (background):
   ```bash
   docker-compose up -d --build
   ```

3. Run database migrations:
   ```bash
   docker-compose exec web python manage.py migrate
   ```

4. Create a superuser:
   ```bash
   docker-compose exec web python manage.py createsuperuser
   ```

## Services

- **web**: Django application (port 8000)
- **celery_worker**: Celery worker for background tasks
- **celery_beat**: Celery beat scheduler for periodic tasks
- **redis**: Redis cache and message broker (port 6379)
- **db**: PostgreSQL database (port 5432)

## Management Script Commands

The `docker-manage.sh` script provides convenient commands:

```bash
./docker-manage.sh start              # Start all services
./docker-manage.sh stop               # Stop all services
./docker-manage.sh logs [service]     # View logs
./docker-manage.sh migrate            # Run migrations
./docker-manage.sh createsuperuser    # Create superuser
./docker-manage.sh test               # Run tests
./docker-manage.sh status             # Show service status
./docker-manage.sh manage <command>   # Run Django management commands
./docker-manage.sh clean              # Clean up all Docker resources
./docker-manage.sh help               # Show help
```

## Environment Variables

All sensitive configuration is stored in the `.env` file:

- `SECRET_KEY`: Django secret key (change in production!)
- `DEBUG`: Set to `False` in production
- `DATABASE_URL`: PostgreSQL connection string
- `CELERY_BROKER_URL`: Redis URL for Celery broker
- `REDIS_URL`: Redis URL for cache/channels

## Production Considerations

- Change `DEBUG=False` in production
- Use a proper `SECRET_KEY`
- Configure proper database credentials
- Set up proper logging
- Use environment-specific settings
- Consider using gunicorn instead of Django's development server
- Add nginx as a reverse proxy
- Set up SSL/TLS certificates

## Volumes

- `postgres_data`: PostgreSQL data persistence
- `redis_data`: Redis data persistence
- `static_volume`: Django static files
- `media_volume`: User uploaded media files