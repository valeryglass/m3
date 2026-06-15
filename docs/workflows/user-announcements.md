# User Announcements

Purpose: centralize alpha-user communication before it becomes bot automation.

## Current Shape

Use this as a workflow first, not a runtime module yet.

```text
release/change -> operator note -> selected alpha users -> observe replies/issues
```

The announcement text is a product artifact. It should be reviewed like UI copy.

## Announcement Types

```text
release_notice      new capability or behavior change
incident_notice     temporary breakage or degraded behavior
maintenance_notice  planned downtime/restart window
experiment_notice   limited test or alpha-only behavior
```

## Rules

- Say what changed in one sentence.
- Say what the user can do now.
- Say what is not supported yet.
- Avoid internal module names, branch names, and commit hashes.
- Do not imply diagnostic or clinical interpretation.
- Do not claim audio is saved if raw audio is temporary-only.

## MVP2 Audio Announcement Template

```text
Новая версия: теперь можно присылать короткие голосовые/аудио до 3–5 минут.
Бот сначала расшифрует аудио, соберёт черновик эпизода и попросит подтвердить
перед сохранением. Если расшифровка не сработает — просто пришлите текстом.
```

Do not claim:

```text
длинные аудио
идеальная расшифровка
анализ голоса/эмоций
сохранение аудио
```

## Future Runtime Module

Only promote this to a bot/admin module when there is a clear need for:

```text
/admin_announce draft
/admin_announce send_to_alpha
announcement delivery log
per-user opt-out or pause rules
```

Until then, keep it as operator workflow and copy templates.
