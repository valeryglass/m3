SYSTEM_PYTHON := python3
VENV := .venv
VENV_PYTHON := $(VENV)/bin/python
VENV_PIP := $(VENV)/bin/pip
BOT_MODULE := app.telegram_bot
BOT_PROCESS_PATTERN := [p]ython[0-9.]* -m app[.]telegram_bot

.PHONY: venv bot bot-pid bot-stop bot-kill bot-restart docker-bot docker-bot-ps docker-bot-stop docker-bot-logs

venv:
	$(SYSTEM_PYTHON) -m venv $(VENV)
	$(VENV_PYTHON) -m pip install -U pip
	$(VENV_PIP) install -e '.[dev,audio]'

bot:
	$(VENV_PYTHON) -m $(BOT_MODULE)

bot-pid:
	@pgrep -af '$(BOT_PROCESS_PATTERN)' || true

bot-stop:
	@pids="$$(pgrep -f '$(BOT_PROCESS_PATTERN)' || true)"; \
	if [ -z "$$pids" ]; then \
		echo "bot not running"; \
	else \
		if kill $$pids; then \
			echo "stopped: $$pids"; \
		else \
			echo "failed to stop: $$pids"; \
			echo "If this is a Docker/root-owned bot, use make docker-bot-stop."; \
			exit 1; \
		fi; \
	fi

bot-kill:
	@pids="$$(pgrep -f '$(BOT_PROCESS_PATTERN)' || true)"; \
	if [ -z "$$pids" ]; then \
		echo "bot not running"; \
	else \
		if kill -9 $$pids; then \
			echo "killed: $$pids"; \
		else \
			echo "failed to kill: $$pids"; \
			echo "If this is a Docker/root-owned bot, use make docker-bot-stop."; \
			exit 1; \
		fi; \
	fi

bot-restart: bot-stop
	$(VENV_PYTHON) -m $(BOT_MODULE)

docker-bot:
	docker compose up -d --build bot

docker-bot-ps:
	docker compose ps bot

docker-bot-stop:
	docker compose stop bot

docker-bot-logs:
	docker compose logs -f bot
