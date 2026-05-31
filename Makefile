PYTHON ?= python3
BOT_MODULE := app.telegram_bot
EPISODE_DIR ?= data/episodes
GRAPH_REPORT_DIR ?= data/reports/graph
CBT_PROFILE_DIR ?= data/reports/cbt-profile
CBT_ANALYTICS_DIR ?= data/reports/cbt-analytics
UX_REPORT_DIR ?= data/reports/ux
ANNOTATION_WORK_DIR ?= data/annotation-work
ANNOTATION_BATCH_SIZE ?= 5
ANNOTATION_SOURCE ?=
PROPOSAL ?= data/annotation-work/proposal.jsonl
REPORT_MIN_COUNT ?= 2

.PHONY: bot bot-pid bot-stop bot-kill bot-restart normalize-episodes audit report-graph report-cbt-profile report-cbt-analytics report-ux reports analytics-ux analytics annotation-audit annotation-queue annotation-validate annotation-apply annotation-apply-write annotation-refresh-reports

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
	$(PYTHON) -m app.graph_report --episode-dir $(EPISODE_DIR) --output-dir $(GRAPH_REPORT_DIR) --by-source --html --min-count $(REPORT_MIN_COUNT)

report-cbt-profile:
	$(PYTHON) -m app.cbt_profile --episode-dir $(EPISODE_DIR) --output-dir $(CBT_PROFILE_DIR) --by-source --min-count $(REPORT_MIN_COUNT)

report-cbt-analytics:
	$(PYTHON) -m app.cbt_analytics --episode-dir $(EPISODE_DIR) --output-dir $(CBT_ANALYTICS_DIR) --by-source --min-count $(REPORT_MIN_COUNT)

report-ux:
	$(PYTHON) -m app.ux_analytics --output-dir $(UX_REPORT_DIR)

reports: normalize-episodes audit report-graph report-cbt-profile report-cbt-analytics report-ux

annotation-refresh-reports: reports

analytics-ux:
	$(PYTHON) -m app.ux_analytics

analytics: analytics-ux
