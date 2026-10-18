# Agno 2 session storage

Before upgrading an existing deployment, stop the web process and all Celery workers, then back up the agent session database configured by `AGENT_SESSION_DB_PATH`. Do not run old and new workers against the same database during cutover.

On startup, `get_podcast_db` copies legacy sessions into `podcast_sessions_v2` using Agno's v1 conversion helpers. It verifies every session, its run count and converted state before switching readers. Invalid data stops startup and leaves the original table in place. Resolve the reported record and restart; partial copies can be retried.

After verification, the original table is retained as `podcast_sessions_v1_backup`. A `podcast_sessions` view presents the existing history, pagination and session-data schema. Its delete trigger removes the current v2 record; restarting does not restore deleted sessions from the backup. The backup retains pre-upgrade records, including subsequently deleted sessions, until the operator removes it under the application's retention policy.

The original database and internal session-state database are not deleted. New runs are saved automatically by Agno. Rollback after new conversations have occurred requires exporting those v2 runs; the legacy backup only contains the state at migration time.

Runtime tests cover a fixture produced by Agno 1.4.2, resumed chat with prior messages, new-run persistence, empty sessions, malformed-data rejection, repeat initialization and deletion. Provider responses are mocked; these tests do not validate live OpenAI credentials or Redis/Celery deployment.
