# Data Model: Multi-Agent Pipeline

## Spec Reference
Implements: `specs/multi-agent-pipeline/spec.md`

## Entities

### learning_gaps (NEW)

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | INTEGER | PK, AUTOINCREMENT | Primary key |
| offer_id | INTEGER | FK offers(id) ON DELETE CASCADE | Associated offer |
| topic | TEXT | NOT NULL | Gap topic (tech_stack, projects, experience, education, english, cultural_fit) |
| gap_detail | TEXT | NOT NULL | Specific gap description |
| severity | TEXT | DEFAULT 'medium' | low / medium / high |
| suggested_action | TEXT | nullable | What to do about it |
| created_at | TEXT | DEFAULT CURRENT_TIMESTAMP | When the gap was recorded |

### offers (EXISTING — no schema changes)

No new columns needed. The `learning_gaps` table references `offers.id` via foreign key.

### offer_topics (EXISTING — no schema changes)

No changes needed.

## Relationships

- `learning_gaps` belongs to `offers` (via `learning_gaps.offer_id`)
- `offers` has many `learning_gaps` (via cascade delete)
- `offers` has many `offer_topics` (existing, unchanged)

## Indexes

| Table | Columns | Type | Rationale |
|-------|---------|------|-----------|
| learning_gaps | offer_id | btree | Lookup gaps by offer |
| learning_gaps | topic | btree | Filter gaps by topic |
| learning_gaps | severity | btree | Filter gaps by severity |

## Constraints

- `CHECK (severity IN ('low', 'medium', 'high'))` on learning_gaps.severity
- `CHECK (topic IN ('tech_stack', 'projects', 'experience', 'education', 'english', 'cultural_fit'))` on learning_gaps.topic

## Migrations

### Migration v4 → v5: Add learning_gaps table

```sql
CREATE TABLE IF NOT EXISTS learning_gaps (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    offer_id        INTEGER REFERENCES offers(id) ON DELETE CASCADE,
    topic           TEXT NOT NULL,
    gap_detail      TEXT NOT NULL,
    severity        TEXT DEFAULT 'medium',
    suggested_action TEXT,
    created_at      TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_learning_gaps_offer_id ON learning_gaps(offer_id);
CREATE INDEX IF NOT EXISTS idx_learning_gaps_topic ON learning_gaps(topic);
CREATE INDEX IF NOT EXISTS idx_learning_gaps_severity ON learning_gaps(severity);
```

- **Rollback:** DROP TABLE IF EXISTS learning_gaps;
