# ADR 002 — SQLite as the storage engine

**Status:** Accepted
**Date:** 2026-08-07 (recorded retroactively; decision made at project start)

## Context

Given [ADR 001](001-local-first.md), storage had to be a local file. The
question was which format.

The access patterns are not just read-and-write. Several commands are
aggregations over the whole dataset:

- `stats` — conversion funnel across all offers, grouped by status
- `gaps` — skills ranked by frequency and total gap, accumulated across offers
- `trends` — applications bucketed by week or month
- `salary` — min/max/average, filtered by role and seniority

There is also a real relationship in the data: an offer has many topic scores
(`offer_topics`), and deleting an offer must delete its topics.

## Decision

SQLite, one database file at `~/.applyr/jobs.db`, accessed exclusively through
`applyr/db.py`.

## Consequences

### Positive

- **Zero dependencies.** `sqlite3` ships in the Python standard library. This
  is the decisive factor — it is the only real database that costs nothing
  against the constraint in [ADR 005](005-single-cli.md).
- **Aggregations are the database's job.** `GROUP BY`, `COUNT`, `AVG` and
  `JOIN` run in C over an indexed file. The alternative is loading every record
  into Python and aggregating by hand in each command.
- **Referential integrity is enforced, not remembered.** `offer_topics` has a
  foreign key with `ON DELETE CASCADE`, and `get_conn()` sets
  `PRAGMA foreign_keys = ON` on every connection.
- **Transactions.** A partially written offer cannot be left behind by an
  interrupted command.
- **Single portable file.** Copying `~/.applyr/jobs.db` is a complete backup.
- **A migration path exists.** `SCHEMA_VERSION` plus `MIGRATIONS` in `db.py`
  handles schema evolution for users already holding data.

### Negative

- Schema changes need a migration, where a JSON file would need none. This is
  real friction, accepted in exchange for the integrity guarantees.
- The data is not human-readable or hand-editable without a SQLite client.
- Concurrent writes are limited, though irrelevant for a single-user CLI.

### Neutral

- Column count is a stable contract (see `docs/contracts.md`), so adding
  fields is deliberate rather than incidental.

## Alternatives considered

**Flat JSON file.** Rejected. Trivially simple to start, but every aggregate
command becomes a full load plus a manual reduction in Python, and cascade
deletes become the author's responsibility to get right on every code path.
Growth makes both worse.

**PostgreSQL.** Rejected. It contradicts [ADR 001](001-local-first.md) — it
requires a server process, which means installation instructions, a connection
string, and something that can be down. Its advantages (concurrency,
replication) address problems a single-user local tracker does not have.

**CSV.** Rejected. No types, no relations, no way to represent `offer_topics`
without a second file and manual joins.

## Notes on a rejected line of reasoning

An early argument for SQLite was that it would make a future migration to a
vector database easier. **This reasoning does not hold and is not why SQLite
was chosen.**

A vector database stores embeddings and indexes by similarity; SQLite stores
rows and indexes by value. Moving from SQLite to Qdrant or pgvector is not
meaningfully easier than moving from JSON — in both cases the actual work is
generating embeddings, which neither format provides.

The accurate forward-looking argument is the opposite one: **SQLite likely
removes the need to migrate at all.** It ships FTS5 for full-text search, and
`sqlite-vec` exists as an extension for vector similarity. If semantic search
over offers is ever wanted, it is an extension away rather than a migration.

Related: [ADR 001](001-local-first.md), [ADR 005](005-single-cli.md).
