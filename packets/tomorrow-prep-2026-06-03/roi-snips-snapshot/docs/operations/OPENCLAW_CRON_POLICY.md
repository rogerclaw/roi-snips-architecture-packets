# OpenClaw Cron Policy

OpenClaw cron `status=ok` means only that the scheduled assistant turn completed. It does not prove a shell command ran.

Roi Snips market-open shell commands must use local shell crontab, launchd, or another proven shell-capable runner. OpenClaw cron may be used for artifact inspection or notification, but it may not be considered an executable scheduler unless a same-surface isolated exec smoke test passes.

A Roi Snips OpenClaw cron run is ready only when all of the following are true:

- Runtime status is `ok`.
- Assistant summary is exactly `OK`.
- The expected artifact exists.
- The expected artifact was modified after the scheduled time.
- The assistant summary does not contain `FAILURE command unavailable`.
