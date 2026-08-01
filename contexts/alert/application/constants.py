"""Application-level constants for the alert context."""

# Sentinel project id meaning "all projects" — used for admins on the
# websocket alert stream and the missed-notification query.
ALL_PROJECTS = -1

# Outbox delivery: a message with no connected subscriber is retried with
# exponential backoff (capped at 300s). It is dropped with a trace after
# OUTBOX_MAX_RETRIES *further* attempts (i.e. 1 initial attempt + N retries)
# — it must never be marked "sent" while nobody could receive it.
OUTBOX_MAX_RETRIES = 10
OUTBOX_SEND_TIMEOUT_SECONDS = 10
