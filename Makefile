.PHONY: help install build start stop restart logs status test dev dev-build dev-stop dev-restart dev-logs mock doctor backup update homeassistant-start homeassistant-stop music-start music-stop

COMPOSE := docker compose
DEV_COMPOSE := $(COMPOSE) -f compose.yaml -f compose.dev.yaml

help:
	@echo "Emily development commands"
	@echo "  make dev          Start the development stack with live reload"
	@echo "  make dev-build    Build the development Core image"
	@echo "  make dev-stop     Stop the development stack"
	@echo "  make dev-restart  Restart the development stack"
	@echo "  make dev-logs     Follow development stack logs"
	@echo "  make mock         Start development with in-memory mock Home Assistant"
	@echo "  make build        Build Emily Core"
	@echo "  make start        Start the standard stack"
	@echo "  make stop         Stop the standard stack"
	@echo "  make restart      Restart the standard stack"
	@echo "  make logs         Follow standard stack logs"
	@echo "  make status       Show standard stack status"
	@echo "  make test         Run the Docker-backed Python test suite"
	@echo "  make doctor       Run diagnostics without displaying secrets"
	@echo "  make backup       Create a backup"
	@echo "  make update       Run the safe updater"
	@echo "  make music-start  Start optional Music Assistant"
	@echo "  make music-stop   Stop optional Music Assistant"
	@echo "  make homeassistant-start  Start optional Home Assistant"
	@echo "  make homeassistant-stop   Stop optional Home Assistant"

install:
	./scripts/install.sh

build:
	$(COMPOSE) build emily-core

start:
	./scripts/start.sh

stop:
	./scripts/stop.sh

restart: stop start

logs:
	./scripts/logs.sh

status:
	$(COMPOSE) ps

test:
	docker build --target test -t emily-core:test services/emily-core
	docker run --rm emily-core:test

dev:
	$(DEV_COMPOSE) up --build

dev-build:
	$(DEV_COMPOSE) build emily-core

dev-stop:
	$(DEV_COMPOSE) stop

dev-restart: dev-stop
	$(DEV_COMPOSE) up --build

dev-logs:
	$(DEV_COMPOSE) logs --tail=100 --follow

mock:
	HOME_ASSISTANT_MOCK=true $(DEV_COMPOSE) up --build

doctor:
	./scripts/doctor.sh

backup:
	./scripts/backup.sh

update:
	./scripts/update.sh

music-start:
	docker compose --profile music up -d music-assistant-server

music-stop:
	docker compose --profile music stop music-assistant-server

homeassistant-start:
	$(COMPOSE) --profile homeassistant up -d homeassistant

homeassistant-stop:
	$(COMPOSE) --profile homeassistant stop homeassistant
