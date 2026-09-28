---
name: test-writer
description: Use whenever writing, changing, or reviewing tests in Waterline (backend or frontend), including the tests inside new-area and migration work. Picks the test layer, enforces assertions that can actually fail, and proves each test catches the bug it names.
---

# Writing tests that can fail

A test exists to catch a specific bug. Coverage is a side effect, not the goal: a test that no
plausible bug would break is worse than no test, because it makes the code look safe.

Read first: `docs/testing-strategy.md` (layers, factories, isolation, gates) and the design-doc
or schema-doc section that defines the behavior you're testing.

## 1. List the behaviors before writing any test

Build this table first, from the docs, not from the code:

| Behavior | Source | Layer | Bug it catches | Proof it fails |
|---|---|---|---|---|
| Member can't delete an approved requirement | design §5 deletion table | unit + API | reporter check ignores `approved_revision_id` | red first: returned True |

Where behaviors come from:
- every row of every table in the relevant design-doc section (roles, transitions, deletion);
- every constraint and index in the schema-doc tables you touch (unique, CHECK, partial index);
- every error response the feature can return (404, 403, 409, 422) and its error `code`;
- every side effect: activity-log entries, deleted sessions, counter increments, cancelled
  approval requests, jobs enqueued.

**Every allowed case gets a denied counterpart row.** Authorization and validation bugs hide in
the cases that should fail.

Include the finished table in the checkpoint summary.

## 2. Choose the layer

Use the cheapest layer that can catch the bug.

| Behavior | Layer |
|---|---|
| Pure logic: transition table, approval policy, key/username validation, rank math | Unit (`tests/unit/`) |
| Queries, org scoping, soft delete, optimistic locking, numbering, `log_change()`, cross-area service calls | Integration (`tests/integration/`) |
| HTTP contract: status codes, error body, cookies, CSRF/Origin, 404-not-403, request validation | API (`tests/api/`) |
| Component rendering, composables, stores, route guards | Vitest |
| A user flow across screens | Playwright (only the slice's critical flows) |

**Wiring tests.** A rule proven in a unit test is only enforced if the endpoint actually calls
it. For every authorization rule and business rule, add at least one API or integration test
showing the real endpoint or service denies the forbidden case.

## 3. Rules for every test

1. **Name the behavior**: `test_member_cannot_delete_approved_requirement`, not
   `test_delete_2`.
2. **Assert the outcome, not only the response.** After a mutation, check:
   - the response (status, error `code`, relevant body fields);
   - persisted state, re-read from the database with a fresh query (not the object the service
     returned);
   - side effects (the `activity_log` row with its `action`, `field_changed`, `old_value`,
     `new_value`, `changed_by`; deleted sessions; counter values);
   - the effect on other people: the other user can now see / no longer see / still use
     something.
3. **Expected values are literals from the spec.** Write `assert display_id == "PMT-TA-45"`,
   never `assert display_id == format_display_id(project, task)`. Computing the expected value
   with the code under test makes the test unable to fail.
4. **Set what you depend on.** Pass every value the test relies on to the factory explicitly
   (`TaskFactory(status=TaskStatus.IN_REVIEW, reviewer=reviewer)`). Never assert a value that
   only the factory set as though the code produced it.
5. **Test boundaries on both sides.** Project key: 3 and 6 characters pass; 2 and 7 fail; a
   leading digit fails; lowercase input is uppercased. Dates: equal, one before, one after.
6. **No logic in tests.** No `if`, no loops over expected values (use `parametrize`), no
   `try/except` (use `pytest.raises(..., match=...)`), no `sleep`.
7. **Assert errors precisely**: the status *and* the error `code`; `pytest.raises(IntegrityError,
   match="<constraint name>")` for database constraints.
8. **One behavior per test.** Parametrize tables (roles, transitions) instead of copying tests.
9. **Real database; mock only the outside world.** Mock outbound HTTP (GitHub) at the `httpx`
   boundary. Never mock the unit under test, repositories, `authorize()`, or `log_change()`.

### Banned patterns

| Pattern | Why it's shallow | Instead |
|---|---|---|
| `assert r.status_code == 200` as the only check | passes if the endpoint does nothing | also assert state and side effects |
| `assert result is not None` as the main check | almost anything passes | assert the specific value |
| Expected value from the code under test | can't fail | literal from the spec |
| Asserting a value the factory set | tests the factory | set it, then assert what the code changed |
| Allowed case with no denied case | misses the bug that matters | add the denied row |
| Unit-tested rule with no wiring test | rule may never be called | add an API/integration test |
| `if`/loops/`try` in a test | hides which case failed | `parametrize`, `pytest.raises` |
| Snapshot as the only frontend assertion | passes whatever renders | assert visible text, state, emitted events |

## 4. Prove each test can fail

- **`rules/` and `authz/`: test first.** Write the test, run it, and watch it fail *for the
  right reason* (a wrong result, not an `ImportError`: create a stub that returns the wrong
  answer if needed). Then implement until green. Record "red first" in the table.
- **Everything else: sabotage check.** For each behavior in the table, make the smallest change
  to the code that breaks it (invert a condition, remove the `log_change()` call, drop the org
  filter, skip the version check, return early), run the related tests, and confirm at least
  one fails. Restore the code and confirm with `git diff` that no sabotage remains (a leftover
  would also fail `wl check`). Record what you broke and which test caught it.
- **If nothing fails, the test is shallow.** Fix the test; don't move on.
- **Mutation testing** (when enabled per `docs/testing-strategy.md`): no surviving mutants in
  `app/rules/` or `app/authz/`. Kill a survivor with a new or sharper test. Only a truly
  equivalent mutant (one that can't change behavior) may be marked `# pragma: no mutate`, with a
  comment explaining why.

## 5. Templates

Fixture and helper names below are illustrative; use the ones in `tests/conftest.py` and
`tests/factories/`.

**Unit — a table from the design doc, both sides:**

```python
@pytest.mark.parametrize(
    ("relationship", "to_status", "allowed"),
    [
        # design-doc §5, task status transitions, from in_review
        ("assignee", TaskStatus.DONE, True),
        ("reviewer", TaskStatus.DONE, True),
        ("other_member", TaskStatus.DONE, False),
        ("reviewer", TaskStatus.IN_PROGRESS, True),
        ("assignee_with_reviewer_set", TaskStatus.IN_PROGRESS, False),
    ],
)
def test_transition_from_in_review(relationship, to_status, allowed):
    assert can_transition(TaskStatus.IN_REVIEW, to_status, relationship) is allowed
```

**Integration — state and side effects, not just the return value:**

```python
async def test_deleting_task_hides_it_and_logs_the_actor(session, member):
    task = await TaskFactory.create_async(project=member.project, reporter=member.user)

    await task_service.delete(actor=member.user, project_key=member.project.key, number=task.number)

    assert await task_repo.get_by_number(member.project, task.number) is None
    stored = await task_repo.get_by_number(member.project, task.number, include_deleted=True)
    assert stored.deleted_at is not None
    log = await activity_repo.for_entity(EntityType.TASK, task.id)
    assert [(e.action, e.changed_by) for e in log] == [(Action.DELETED, member.user.id)]
```

**API — tenant isolation (a test every new endpoint needs):**

```python
async def test_task_is_404_for_user_in_another_org(client_for, task, outsider):
    r = await client_for(outsider).get(f"/api/projects/{task.project.key}/tasks/{task.number}")

    assert r.status_code == 404
    assert r.json()["code"] == "not_found"
    assert task.title not in r.text
```

**Concurrency (`@pytest.mark.concurrency`) — parallel transactions, real commits:**

```python
@pytest.mark.concurrency
async def test_parallel_allocations_never_collide(project, separate_sessions):
    numbers = await gather_in_parallel(
        [allocate_number_in(s, project, "TA") for s in separate_sessions(20)]
    )
    assert sorted(numbers) == list(range(1, 21))
```

**Property (Hypothesis) — invariants over many inputs:**

```python
@given(st.lists(st.tuples(st.integers(0, 50), st.integers(0, 50)), max_size=100))
def test_rank_keys_always_sort_between_their_neighbors(moves):
    order = apply_moves(initial_order(), moves)
    assert order == sorted(order, key=lambda item: (item.rank, item.id))
```

**Frontend (Vitest):** mount the component with the typed API client mocked, then assert what
the user sees and can do: text, disabled/hidden actions, emitted events, the 409 reload prompt,
field errors from a 422. Never assert on internal component state.

**Playwright:** only the flows in the slice's "Done when" list, against the full stack.

## 6. Done checklist

- [ ] Behavior table complete, with denied rows and a source for each behavior.
- [ ] Each behavior tested at the cheapest layer that catches it, plus wiring tests for rules.
- [ ] "Proof it fails" filled in for every row (red first, sabotage, or killed mutant).
- [ ] No banned patterns.
- [ ] `uv run wl check` green.
