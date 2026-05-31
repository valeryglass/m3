PYTHON ?= python3
BOT_MODULE := app.telegram_bot
EPISODE_DIR ?= data/episodes
ANNOTATION_WORK_DIR ?= data/annotation-work
ANNOTATION_BATCH_SIZE ?= 5
ANNOTATION_SOURCE ?=
PROPOSAL ?= data/annotation-work/proposal.jsonl

.PHONY: bot bot-pid bot-stop bot-kill bot-restart normalize-episodes audit annotation-audit annotation-queue annotation-validate annotation-apply annotation-apply-write

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
