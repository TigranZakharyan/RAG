.PHONY: dev prod dev-build prod-build dev-down prod-down dev-logs prod-logs clean

# =========================
# Development
# =========================

dev:
	docker compose --env-file .env.development -f docker-compose.dev.yml up

dev-build:
	docker compose --env-file .env.development -f docker-compose.dev.yml up --build

dev-down:
	docker compose --env-file .env.development -f docker-compose.dev.yml down

dev-logs:
	docker compose --env-file .env.development -f docker-compose.dev.yml logs -f


# =========================
# Production
# =========================

prod:
	docker compose --env-file .env.production -f docker-compose.prod.yml up -d

prod-build:
	docker compose --env-file .env.production -f docker-compose.prod.yml up --build -d

prod-down:
	docker compose --env-file .env.production -f docker-compose.prod.yml down

prod-logs:
	docker compose --env-file .env.production -f docker-compose.prod.yml logs -f


# =========================
# Cleanup
# =========================

clean:
	docker system prune -f