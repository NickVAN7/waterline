---
name: migration
description: Use for any Waterline database schema change (new or altered tables, columns, constraints, indexes, enum values) and for data migrations. Covers model changes, generating the Alembic migration, hand-reviewing what autogenerate misses, the downgrade, constraint tests, and keeping schema-doc.md in sync.
---

# Schema changes and migrations

`docs/schema-doc.md` is the source of truth for tables. The model follows the doc; the migration
follows the model; tests prove the database enforces what the doc says.

## 1. Start from the schema doc

- Read the schema-doc section for every table you touch, plus the conventions at the top of the
  doc (UUIDv7, timestamps, enums, soft delete).
- If the change isn't in the doc yet, stop: it needs the owner's approval, and the doc is
  updated in the same commit (see "Docs" below).
- **Columns added in a later slice.** A schema-doc column whose Notes cell starts with
  `Added in Slice <n>.` is built in slice `<n>`, not with its table. When adding a table, leave
  out its marked columns from later slices. In slice `<n>`, add every column marked
  `Added in Slice <n>.` (search the schema doc for it), usually with the table it references:
  once the slice's last checkpoint is committed, the docs consistency tests require the column,
  so it must land within the slice.

## 2. Change the models

- Use the shared base and mixins (UUIDv7 `id`, `created_at`/`updated_at`, soft delete,
  `version` for optimistic locking, `ClassificationMixin` where the schema doc calls for it)
  rather than declaring those columns by hand.
- Enums through the enum helper only (`native_enum=False`, `create_constraint=True`); without
  `create_constraint` there is no CHECK.
- Relationships default to `lazy="raise"`.
- Constraints and indexes are declared on the model (`__table_args__`), so the model and the
  migration can be compared.

## 3. Generate

```
uv run wl backend migration "<imperative message, e.g. add phase table>"
```

Prefer one migration per checkpoint. An **uncommitted** migration may be deleted and regenerated
freely; a **committed** one is never edited (a hook blocks it): fix forward with a new migration.

## 4. Review by hand: what autogenerate misses or gets wrong

Open the generated file and check each item against the schema doc:

- [ ] **Every column**: type, nullability, and default match the doc. Python-side defaults
      (`default=`) don't exist in the database; use `server_default` where the database must
      supply a value.
- [ ] **Enum CHECK constraints appear once each.** For a non-native enum, autogenerate emits
      the CHECK up to three times: the column's `sa.Enum(..., create_constraint=True)`, a
      `sa.CheckConstraint(..., name="<column>")` with an ad-hoc name, and the named
      `op.f("ck_<table>_<column>")` one. Keep only the named one: set
      `create_constraint=False` on the column's `sa.Enum` and delete the ad-hoc copy (found in
      S1-C1).
- [ ] **Enum CHECK constraints** are present and list every value. Autogenerate does **not**
      detect changes to CHECK constraints: adding, renaming, or removing an enum value needs
      hand-written `op.drop_constraint` + `op.create_check_constraint` (plus a data `UPDATE` for
      renames, and a check that no rows use a removed value).
- [ ] **Other CHECK constraints** from the doc (e.g. `end_date >= start_date`,
      `task_id <> depends_on_task_id`, the `approval_request` revision check) are present.
- [ ] **Partial unique indexes** (`postgresql_where=...`), e.g. one active sprint per project,
      one pending approval request per entity. Autogenerate may not detect a changed `WHERE`
      clause; compare it by eye.
- [ ] **Generated columns** (`search_vector` as `sa.Computed(..., persisted=True)`) and their
      **GIN indexes** (`postgresql_using="gin"`). Changes to a computed expression are not
      detected.
- [ ] **Constraint names** come from the naming convention; no `None` names and no ad-hoc names.
- [ ] **Foreign keys** point at the right table and have the intended `ondelete` behavior
      (usually none: rows are soft-deleted, not removed).
- [ ] **Adding a NOT NULL column to a table with data**: add it nullable, backfill, then set
      NOT NULL (or give it a `server_default`). Tests start from an empty database, so this
      mistake won't show up there.
- [ ] **No unrelated changes**: procrastinate's tables are excluded from autogenerate; nothing
      else outside this change appears.

## 5. Data migrations

- Don't import app models (they will change later and break old migrations). Use lightweight
  table stubs (`sa.table(...)`) or `op.execute(...)` with bound parameters.
- Keep the schema change and the data change in clear, separate steps within the migration.

## 6. Downgrade

- The downgrade reverses the upgrade exactly, in reverse order.
- If the downgrade can't restore data (e.g. a dropped column), it must still restore the
  schema; say so in a comment.

## 7. Test

- `uv run wl migrate` applies it to the dev database.
- The migration checks in `uv run wl check` must pass: upgrade from empty, downgrade one step
  and upgrade again, no autogenerate drift.
- **Drift checks can't see CHECK or partial-index differences**, so every unique constraint,
  CHECK constraint, and partial unique index added in this migration gets an integration test
  that writes a violating row and expects `IntegrityError` naming that constraint. Follow the
  `test-writer` skill.

## 8. Docs

- Update `docs/schema-doc.md` in the same commit: columns, notes, constraints, and indexes
  match what the migration creates, and nothing in the doc is missing from the migration.
- If the ER diagram's relationships changed, update it too.
