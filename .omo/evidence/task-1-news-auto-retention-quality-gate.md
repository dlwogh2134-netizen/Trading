# Task 1 Evidence - News Quality Metadata Migration

## Scope
- Todo: `1. Add Supabase quality metadata and retention indexes`
- Changed migration: `supabase/migrations/20260716151440_add_news_quality_metadata_retention_indexes.sql`
- Production database mutation: not performed.

## Implementation Observable
- Scenario: migration file contains the requested nullable quality metadata columns.
- Invocation: `rg -n "relevance_score|quality_status|excluded_reason|quality_checked_at|news_articles_quality_status_check|idx_news_articles_quality_status_published_at|idx_news_articles_symbol_quality_status_published_at|idx_news_fetch_logs_started_at" "supabase\migrations\20260716151440_add_news_quality_metadata_retention_indexes.sql"`
- Result summary: found all four columns, the `news_articles_quality_status_check` constraint, and all three requested indexes.

## Supabase MCP Schema Inspection
- Scenario: inspect existing remote schema only before migration application.
- Tool invocation: `mcp__codex_apps__supabase._list_tables(project_id="fdvhoaytcqnswuebocmr", schemas=["public"], verbose=true)`
- Result summary: `public.news_articles` and `public.news_fetch_logs` exist. Current remote `news_articles` did not include `relevance_score`, `quality_status`, `excluded_reason`, or `quality_checked_at`.
- Tool invocation: `mcp__codex_apps__supabase._execute_sql` with read-only `information_schema.columns`, `pg_indexes`, and `pg_constraint` catalog queries for the new column/index/constraint names.
- Result summary: all three read-only catalog queries returned `[]`, confirming the remote schema has not already applied this Todo 1 migration. No DDL was run through MCP.

## SQL Syntax Validation
- Scenario: validate migration syntax locally without applying production DDL.
- Invocation: temporary npm directory outside the repo, `npm install pgsql-ast-parser@12.0.2 --no-audit --no-fund`, then `node -e "... parse(migrationSql) ..."`
- Binary observable: `pgsql-ast-parser parsed migration successfully`
- Invocation: temporary npm directory outside the repo, `npm install libpg-query@17.7.3 --no-audit --no-fund`, then `node -e "... await pg.loadModule(); pg.parseSync(migrationSql) ..."`
- Binary observable: `libpg-query parsed statements: 5`

## Local DB Availability Checks
- Invocation: `supabase --version`
- Result summary: failed, `supabase` command is not installed.
- Invocation: `psql --version`
- Result summary: failed, `psql` command is not installed.
- Invocation: ephemeral `docker run --rm --name ... postgres:17-alpine` validation script.
- Result summary: failed before DB startup because Docker Desktop daemon was unavailable: `failed to connect to the docker API ... dockerDesktopLinuxEngine ... The system cannot find the file specified.`

## Adversarial Notes
- Destructive SQL: migration only adds nullable columns, adds a check constraint, and creates indexes. It contains no `DROP`, `DELETE`, `UPDATE`, `TRUNCATE`, or data backfill.
- Stale state: MCP inspection is a point-in-time remote catalog read before applying this migration; it proves the migration is needed, not that production has the new objects.
- Misleading success output: multi-statement MCP `_execute_sql` returned only the first result set, so the catalog checks were rerun as separate single-result read-only queries.
- Dirty worktree: pre-existing unrelated modified backend/test files and untracked `.omo` items were present. This task touched only the scoped migration, this evidence file, and the Todo 1 checkbox.

## Acceptance Result
- Passed for this executor scope: migration created and native SQL parsing passed.
- Constraint rejection runtime scenario was not executed because no local Postgres/Supabase database was available, and production DDL was explicitly out of scope.
