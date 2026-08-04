.PHONY: install start stop restart logs test doctor backup update music-start music-stop

install:
	./scripts/install.sh

start:
	./scripts/start.sh

stop:
	./scripts/stop.sh

restart: stop start

logs:
	./scripts/logs.sh

test:
	cd services/emily-core && python3 -m pytest

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
