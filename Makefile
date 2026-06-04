PYTHON ?= python3
BOT_MODULE := app.telegram_bot
EPISODE_DIR ?= data/episodes
GRAPH_REPORT_DIR ?= data/reports/graph
PSY_PAYLOAD_DIR ?= data/reports/psy-payload
MAP_PAYLOAD_DIR ?= data/reports/map-payload
UX_REPORT_DIR ?= data/reports/ux
ANNOTATION_WORK_DIR ?= data/annotation-work
ANNOTATION_BATCH_SIZE ?= 5
ANNOTATION_SOURCE ?=
PROPOSAL ?= data/annotation-work/proposal.jsonl
REPORT_MIN_COUNT ?= 2
MAP_SOURCE ?= telegram-chat:327002663
MAP_SOURCE_SAFE ?= $(subst :,-,$(subst /,-,$(MAP_SOURCE)))

.PHONY: bot bot-pid bot-stop bot-kill bot-restart normalize-episodes audit report-graph report-psy-payload report-map-payload report-map-html report-ux reports analytics-ux analytics annotation-audit annotation-queue annotation-validate annotation-apply annotation-apply-write annotation-refresh-reports

bot:
	$(PYTHON) -m $(BOT_MODULE)

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

normalize-episodes:
	$(PYTHON) -m app.derived_normalizer $(EPISODE_DIR) --write

audit:
	$(PYTHON) -m app.annotation_workflow audit --episode-dir $(EPISODE_DIR)

annotation-audit:
	$(PYTHON) -m app.annotation_workflow audit --episode-dir $(EPISODE_DIR)

annotation-queue:
	$(PYTHON) -m app.annotation_workflow queue --episode-dir $(EPISODE_DIR) --work-dir $(ANNOTATION_WORK_DIR) --batch-size $(ANNOTATION_BATCH_SIZE) $(if $(ANNOTATION_SOURCE),--source $(ANNOTATION_SOURCE),)

annotation-validate:
	$(PYTHON) -m app.annotation_workflow validate $(PROPOSAL)

annotation-apply:
	$(PYTHON) -m app.annotation_workflow apply $(PROPOSAL)

annotation-apply-write:
	$(PYTHON) -m app.annotation_workflow apply $(PROPOSAL) --write

report-graph:
	$(PYTHON) -m app.graph_report --episode-dir $(EPISODE_DIR) --output-dir $(GRAPH_REPORT_DIR) --by-source --min-count $(REPORT_MIN_COUNT)

report-psy-payload:
	$(PYTHON) -m app.psy_payload --episode-dir $(EPISODE_DIR) --output-dir $(PSY_PAYLOAD_DIR) --by-source --min-count $(REPORT_MIN_COUNT)

report-map-payload:
	$(PYTHON) -m app.map_payload --episode-dir $(EPISODE_DIR) --source $(MAP_SOURCE) --output $(MAP_PAYLOAD_DIR)/$(MAP_SOURCE_SAFE).json

report-map-html:
	$(PYTHON) -m app.map_payload_html --input $(MAP_PAYLOAD_DIR)/$(MAP_SOURCE_SAFE).json --output $(MAP_PAYLOAD_DIR)/$(MAP_SOURCE_SAFE).html

report-ux:
	$(PYTHON) -m app.ux_analytics --output-dir $(UX_REPORT_DIR)

reports: normalize-episodes audit report-graph report-psy-payload report-ux

annotation-refresh-reports: reports

analytics-ux:
	$(PYTHON) -m app.ux_analytics

analytics: analytics-ux
