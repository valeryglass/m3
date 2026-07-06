PYTHON ?= python3
VENV ?= .venv
VENV_PYTHON := $(VENV)/bin/python
VENV_PIP := $(VENV)/bin/pip
WHISPER_COMMAND ?= $(if $(M3_WHISPER_COMMAND),$(M3_WHISPER_COMMAND),$(VENV)/bin/whisper)
BOT_MODULE := app.telegram_bot
BOT_PROCESS_PATTERN := [p]ython[0-9.]* -m app[.]telegram_bot
EPISODE_DIR ?= data/episodes
ANNOTATION_RUN_ROOT ?= data/annotation-runs
GRAPH_REPORT_EXPORT_DIR ?= data/reports/graph
INSIGHT_PAYLOAD_EXPORT_DIR ?= data/exports/insight-payload
MAP_PAYLOAD_EXPORT_DIR ?= data/exports/map-payload
UX_REPORT_EXPORT_DIR ?= data/reports/ux
REPORT_MIN_COUNT ?= 2
MAP_SOURCE ?= telegram-chat:327002663
MAP_SOURCE_SAFE ?= $(subst :,-,$(subst /,-,$(MAP_SOURCE)))
ANNOTATION_RUN_DIR ?=
ANNOTATION_SOURCE ?=

.PHONY: venv compile test test-docs check check-whisper release-audio-check bot docker-bot bot-pid bot-ps bot-stop bot-kill bot-sudo-stop bot-sudo-kill bot-restart legacy-normalize-episodes-write fresh-analytics-status audit annotation-dry-run annotation-missing annotation-full export-graph-report export-insight-payload export-map-payload export-map-html export-ux-report export-debug-reports beta-report-qa beta-analytics analytics-ux analytics

venv:
	$(PYTHON) -m venv $(VENV)
	$(VENV_PYTHON) -m pip install -U pip
	$(VENV_PIP) install -e '.[dev,audio]'

compile:
	$(VENV_PYTHON) -m py_compile app/*.py app/schemas/*.py

test:
	$(VENV_PYTHON) -m pytest -q

test-docs:
	$(VENV_PYTHON) -m pytest tests/test_project_inventory.py tests/test_roles.py -q

check: compile test

check-whisper:
	@command -v ffmpeg >/dev/null 2>&1 || { \
		echo "missing ffmpeg command"; \
		echo "Install ffmpeg on the runtime host before audio smoke."; \
		exit 1; \
	}
	@command -v "$(WHISPER_COMMAND)" >/dev/null 2>&1 || { \
		echo "missing Whisper command: $(WHISPER_COMMAND)"; \
		echo "Run make venv or set M3_WHISPER_COMMAND=/path/to/whisper."; \
		exit 1; \
	}
	@echo "ffmpeg command available"
	@echo "Whisper command available: $(WHISPER_COMMAND)"

release-audio-check: check test-docs check-whisper

bot:
	$(PYTHON) -m $(BOT_MODULE)

docker-bot:
	docker compose up bot

bot-pid:
	@pgrep -af '$(BOT_PROCESS_PATTERN)' || true

bot-ps:
	@pids="$$(pgrep -f '$(BOT_PROCESS_PATTERN)' || true)"; \
	if [ -z "$$pids" ]; then \
		echo "bot not running"; \
	else \
		pid_list="$$(printf '%s\n' $$pids | paste -sd, -)"; \
		ps -o pid,ppid,user,uid,euid,stat,etime,cmd -p "$$pid_list"; \
	fi

bot-stop:
	@pids="$$(pgrep -f '$(BOT_PROCESS_PATTERN)' || true)"; \
	if [ -z "$$pids" ]; then \
		echo "bot not running"; \
	else \
		if kill $$pids; then \
			echo "stopped: $$pids"; \
		else \
			echo "failed to stop: $$pids"; \
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
			exit 1; \
		fi; \
	fi

bot-sudo-stop:
	@pids="$$(pgrep -f '$(BOT_PROCESS_PATTERN)' || true)"; \
	if [ -z "$$pids" ]; then \
		echo "bot not running"; \
	else \
		if sudo kill $$pids; then \
			echo "stopped with sudo: $$pids"; \
		else \
			echo "failed to stop with sudo: $$pids"; \
			exit 1; \
		fi; \
	fi

bot-sudo-kill:
	@pids="$$(pgrep -f '$(BOT_PROCESS_PATTERN)' || true)"; \
	if [ -z "$$pids" ]; then \
		echo "bot not running"; \
	else \
		if sudo kill -9 $$pids; then \
			echo "killed with sudo: $$pids"; \
		else \
			echo "failed to kill with sudo: $$pids"; \
			exit 1; \
		fi; \
	fi

bot-restart: bot-stop
	$(PYTHON) -m $(BOT_MODULE)

legacy-normalize-episodes-write:
	$(PYTHON) -m app.derived_normalizer $(EPISODE_DIR) --write

fresh-analytics-status:
	$(PYTHON) -m app.fresh_analytics_status --episode-dir $(EPISODE_DIR) --annotation-run-root $(ANNOTATION_RUN_ROOT) $(if $(ANNOTATION_RUN_DIR),--annotation-run-dir $(ANNOTATION_RUN_DIR),) $(if $(ANNOTATION_SOURCE),--source $(ANNOTATION_SOURCE),)

audit:
	$(PYTHON) -m app.annotation_audit --episode-dir $(EPISODE_DIR) --annotation-run-root $(ANNOTATION_RUN_ROOT) $(if $(ANNOTATION_RUN_DIR),--annotation-run-dir $(ANNOTATION_RUN_DIR),)

annotation-dry-run:
	$(PYTHON) -m app.annotation_producer run --episode-dir $(EPISODE_DIR) --output-root $(ANNOTATION_RUN_ROOT) $(if $(ANNOTATION_SOURCE),--source $(ANNOTATION_SOURCE),) --dry-run

annotation-missing:
	@test -n "$(ANNOTATION_RUN_DIR)" || { echo "set ANNOTATION_RUN_DIR to an explicit base run"; exit 1; }
	$(PYTHON) -m app.annotation_producer run --episode-dir $(EPISODE_DIR) --output-root $(ANNOTATION_RUN_ROOT) --only-missing --annotation-run-dir $(ANNOTATION_RUN_DIR) $(if $(ANNOTATION_SOURCE),--source $(ANNOTATION_SOURCE),) --write

annotation-full:
	$(PYTHON) -m app.annotation_producer run --episode-dir $(EPISODE_DIR) --output-root $(ANNOTATION_RUN_ROOT) $(if $(ANNOTATION_SOURCE),--source $(ANNOTATION_SOURCE),) --write

export-graph-report:
	$(PYTHON) -m app.graph_report --episode-dir $(EPISODE_DIR) --output-dir $(GRAPH_REPORT_EXPORT_DIR) --by-source --min-count $(REPORT_MIN_COUNT) $(if $(ANNOTATION_RUN_DIR),--annotation-run-dir $(ANNOTATION_RUN_DIR),)

export-insight-payload:
	@test -n "$(ANNOTATION_RUN_DIR)" || { echo "set ANNOTATION_RUN_DIR to an explicit run"; exit 1; }
	$(PYTHON) -m app.insight_payload --episode-dir $(EPISODE_DIR) --annotation-run-dir $(ANNOTATION_RUN_DIR) --source $(MAP_SOURCE) --output $(INSIGHT_PAYLOAD_EXPORT_DIR)/$(MAP_SOURCE_SAFE).json

export-map-payload:
	@test -n "$(ANNOTATION_RUN_DIR)" || { echo "set ANNOTATION_RUN_DIR to an explicit run"; exit 1; }
	$(PYTHON) -m app.map_payload --episode-dir $(EPISODE_DIR) --annotation-run-dir $(ANNOTATION_RUN_DIR) --source $(MAP_SOURCE) --output $(MAP_PAYLOAD_EXPORT_DIR)/$(MAP_SOURCE_SAFE).json

export-map-html:
	$(PYTHON) -m app.map_payload_html --input $(MAP_PAYLOAD_EXPORT_DIR)/$(MAP_SOURCE_SAFE).json --output $(MAP_PAYLOAD_EXPORT_DIR)/$(MAP_SOURCE_SAFE).html

export-ux-report:
	$(PYTHON) -m app.ux_analytics --output-dir $(UX_REPORT_EXPORT_DIR)

export-debug-reports: audit export-graph-report export-ux-report

beta-report-qa:
	@test -n "$(ANNOTATION_RUN_DIR)" || { echo "set ANNOTATION_RUN_DIR to an explicit run"; exit 1; }
	$(PYTHON) -m app.report_payload_qa --episode-dir $(EPISODE_DIR) --annotation-run-dir $(ANNOTATION_RUN_DIR) --source $(MAP_SOURCE) --insight-payload-path $(INSIGHT_PAYLOAD_EXPORT_DIR)/$(MAP_SOURCE_SAFE).json --map-payload-path $(MAP_PAYLOAD_EXPORT_DIR)/$(MAP_SOURCE_SAFE).json

beta-analytics:
	@test -n "$(ANNOTATION_RUN_DIR)" || { echo "set ANNOTATION_RUN_DIR to an explicit run"; exit 1; }
	$(MAKE) audit ANNOTATION_RUN_DIR=$(ANNOTATION_RUN_DIR)
	$(MAKE) export-graph-report ANNOTATION_RUN_DIR=$(ANNOTATION_RUN_DIR)
	$(MAKE) export-insight-payload ANNOTATION_RUN_DIR=$(ANNOTATION_RUN_DIR)
	$(MAKE) export-map-payload ANNOTATION_RUN_DIR=$(ANNOTATION_RUN_DIR)
	$(MAKE) export-map-html ANNOTATION_RUN_DIR=$(ANNOTATION_RUN_DIR)
	$(MAKE) export-ux-report ANNOTATION_RUN_DIR=$(ANNOTATION_RUN_DIR)
	$(MAKE) beta-report-qa ANNOTATION_RUN_DIR=$(ANNOTATION_RUN_DIR)

analytics-ux:
	$(PYTHON) -m app.ux_analytics

analytics: analytics-ux
