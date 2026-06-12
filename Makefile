PYTHON ?= python3
BOT_MODULE := app.telegram_bot
EPISODE_DIR ?= data/episodes
GRAPH_REPORT_EXPORT_DIR ?= data/reports/graph
MAP_PAYLOAD_EXPORT_DIR ?= data/exports/map-payload
UX_REPORT_EXPORT_DIR ?= data/reports/ux
REPORT_MIN_COUNT ?= 2
MAP_SOURCE ?= telegram-chat:327002663
MAP_SOURCE_SAFE ?= $(subst :,-,$(subst /,-,$(MAP_SOURCE)))

.PHONY: bot docker-bot bot-pid bot-stop bot-kill bot-restart legacy-normalize-episodes-write audit export-graph-report export-map-payload export-map-html export-ux-report export-debug-reports analytics-ux analytics

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
