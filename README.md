# Waterline

A project management and reporting tool for software projects and ERP implementations:
requirements, tasks, phases, test cycles, sign-offs, and status reporting, with traceability
from requirement to sign-off. (Working name. Most of an iceberg sits below the waterline, and
so does most of a project.)

## Quick start

Needs Git, Docker, uv, and Node 22.

```bash
uv sync --all-packages
uv run wl doctor            # check your toolchain
npm ci --prefix frontend    # frontend tools
cp .env.example .env
uv run wl up                # the stack: http://localhost:5173
uv run wl check             # everything CI runs
```

Full setup, commands, and conventions: [docs/developer-guide.md](docs/developer-guide.md).

## Docs

| Doc | Holds |
|---|---|
| [design-doc.md](docs/design-doc.md) | Product direction and design decisions |
| [schema-doc.md](docs/schema-doc.md) | Tables, columns, constraints, indexes |
| [build-plan.md](docs/build-plan.md) | Slices, checkpoints, architecture |
| [testing-strategy.md](docs/testing-strategy.md) | Test layers and gates |
| [developer-guide.md](docs/developer-guide.md) | Setup, commands, how-tos |
| [user-guide.md](docs/user-guide.md) | Using the app |
| [tech-debt.md](docs/tech-debt.md) | Known shortcuts and when they get fixed |
| [reviews/](docs/reviews/) | Each checkpoint's independent review record |
