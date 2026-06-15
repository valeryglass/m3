PYTHON ?= python3
VENV ?= .venv
VENV_PYTHON := $(VENV)/bin/python
VENV_PIP := $(VENV)/bin/pip
WHISPER_COMMAND ?= $(if $(M3_WHISPER_COMMAND),$(M3_WHISPER_COMMAND),whisper)
BOT_MODULE := app.telegram_bot
EPISODE_DIR ?= data/episodes
GRAPH_REPORT_EXPORT_DIR ?= data/reports/graph
MAP_PAYLOAD_EXPORT_DIR ?= data/exports/map-payload
UX_REPORT_EXPORT_DIR ?= data/reports/ux
REPORT_MIN_COUNT ?= 2
MAP_SOURCE ?= telegram-chat:327002663
MAP_SOURCE_SAFE ?= $(subst :,-,$(subst /,-,$(MAP_SOURCE)))

.PHONY: venv compile test test-docs check check-whisper release-audio-check bot docker-bot bot-pid bot-stop bot-kill bot-restart legacy-normalize-episodes-write audit export-graph-report export-map-payload export-map-html export-ux-report export-debug-reports analytics-ux analytics

venv:
	$(PYTHON) -m venv $(VENV)
	$(VENV_PYTHON) -m pip install -U pip
	$(VENV_PIP) install -e '.[dev]'

compile:
	$(VENV_PYTHON) -m py_compile app/*.py app/schemas/*.py

test:
	$(VENV_PYTHON) -m pytest -q

test-docs:
	$(VENV_PYTHON) -m pytest tests/test_project_inventory.py tests/test_roles.py -q

check: compile test

check-whisper:
	@command -v "$(WHISPER_COMMAND)" >/dev/null 2>&1 || { \
		echo "missing Whisper command: $(WHISPER_COMMAND)"; \
		echo "Install Whisper on the runtime host or set M3_WHISPER_COMMAND=/path/to/whisper."; \
		exit 1; \
	}
	@echo "Whisper command available: $(WHISPER_COMMAND)"

release-audio-check: check test-docs check-whisper

bot:
	$(PYTHON) -m $(BOT_MODULE)

docker-bot:
	docker compose up bot

bot-pid:
	@pgrep -af '$(BOT_MODULE)' || true

bot-stop:
	@pids="$$(pgrep -f '$(BOT_MODULE)' || true)"; \
	if [ -z "$$pids" ]; then \
		echo "bot not running"; \
	else \
		kill $$pids; \
		echo "stopped: $$pids"; \
	fi

bot-kill:
	@pids="$$(pgrep -f '$(BOT_MODULE)' || true)"; \
	if [ -z "$$pids" ]; then \
		echo "bot not running"; \
	else \
		kill -9 $$pids; \
		echo "killed: $$pids"; \
	fi

bot-restart: bot-stop
	$(PYTHON) -m $(BOT_MODULE)

legacy-normalize-episodes-write:
	$(PYTHON) -m app.derived_normalizer $(EPISODE_DIR) --write

audit:
	$(PYTHON) -m app.annotation_audit --episode-dir $(EPISODE_DIR)

export-graph-report:
	$(PYTHON) -m app.graph_report --episode-dir $(EPISODE_DIR) --output-dir $(GRAPH_REPORT_EXPORT_DIR) --by-source --min-count $(REPORT_MIN_COUNT)

export-map-payload:
	$(PYTHON) -m app.map_payload --episode-dir $(EPISODE_DIR) --source $(MAP_SOURCE) --output $(MAP_PAYLOAD_EXPORT_DIR)/$(MAP_SOURCE_SAFE).json

export-map-html:
	$(PYTHON) -m app.map_payload_html --input $(MAP_PAYLOAD_EXPORT_DIR)/$(MAP_SOURCE_SAFE).json --output $(MAP_PAYLOAD_EXPORT_DIR)/$(MAP_SOURCE_SAFE).html

export-ux-report:
	$(PYTHON) -m app.ux_analytics --output-dir $(UX_REPORT_EXPORT_DIR)

export-debug-reports: audit export-graph-report export-ux-report

analytics-ux:
	$(PYTHON) -m app.ux_analytics

analytics: analytics-ux
