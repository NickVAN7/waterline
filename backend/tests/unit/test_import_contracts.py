"""The import-linter contracts in pyproject.toml catch each kind of violation they exist for.

Each case copies the app into a temporary directory, adds one offending module, and runs
`lint-imports` against the copy with the real configuration.
"""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[2]
LINT_IMPORTS = Path(sys.executable).parent / "lint-imports"


def lint_copy(tmp_path: Path, files: dict[str, str]) -> subprocess.CompletedProcess[str]:
    shutil.copytree(BACKEND / "app", tmp_path / "app")
    shutil.copy(BACKEND / "pyproject.toml", tmp_path / "pyproject.toml")
    for relative, source in files.items():
        (tmp_path / relative).write_text(source)
    return subprocess.run(  # noqa: S603 -- fixed executable from this venv, no shell
        [str(LINT_IMPORTS), "--no-cache"],
        cwd=tmp_path,
        env={"PYTHONPATH": str(tmp_path)},
        capture_output=True,
        text=True,
        check=False,
    )


def test_current_app_keeps_every_contract(tmp_path: Path) -> None:
    result = lint_copy(tmp_path, {})

    assert result.returncode == 0, result.stdout


@pytest.mark.parametrize(
    ("files", "broken_contract"),
    [
        pytest.param(
            {"app/models/widget.py": "import app.services\n"},
            "Layers: routers -> services -> repositories -> models",
            id="model-imports-service",
        ),
        pytest.param(
            {"app/repositories/widget.py": "import app.services\n"},
            "Layers: routers -> services -> repositories -> models",
            id="repository-imports-service",
        ),
        pytest.param(
            {"app/routers/widget.py": "import app.repositories\n"},
            "Routers never touch repositories or models directly",
            id="router-imports-repository",
        ),
        pytest.param(
            {"app/routers/widget.py": "import app.models\n"},
            "Routers never touch repositories or models directly",
            id="router-imports-model",
        ),
        pytest.param(
            {"app/rules/widget.py": "import sqlalchemy\n"},
            "Rules are pure: no database, no other layers",
            id="rule-imports-sqlalchemy",
        ),
        pytest.param(
            {"app/rules/widget.py": "import app.repositories\n"},
            "Rules are pure: no database, no other layers",
            id="rule-imports-repository",
        ),
        pytest.param(
            {"app/rules/widget.py": "import app.models\n"},
            "Rules are pure: no database, no other layers",
            id="rule-imports-model",
        ),
        pytest.param(
            {
                "app/core/db.py": "import sqlalchemy\n",
                "app/rules/widget.py": "import app.core.db\n",
            },
            "Rules are pure: no database, no other layers",
            id="rule-reaches-sqlalchemy-indirectly",
        ),
        pytest.param(
            {"app/authz/widget.py": "import app.services\n"},
            "authz and audit sit below services",
            id="authz-imports-service",
        ),
        pytest.param(
            {"app/rules/widget.py": "import psycopg\n"},
            "Rules are pure: no database, no other layers",
            id="rule-imports-psycopg",
        ),
        pytest.param(
            {"app/rules/widget.py": "import procrastinate\n"},
            "Rules are pure: no database, no other layers",
            id="rule-imports-procrastinate",
        ),
        pytest.param(
            {
                "app/jobs/widget.py": "import app.services\n",
                "app/authz/widget.py": "import app.jobs.widget\n",
            },
            "authz and audit sit below services",
            id="authz-reaches-service-through-jobs",
        ),
        pytest.param(
            {"app/audit/widget.py": "import app.routers\n"},
            "authz and audit sit below services",
            id="audit-imports-router",
        ),
        pytest.param(
            {"app/jobs/widget.py": "import app.routers\n"},
            "Jobs never import routers",
            id="job-imports-router",
        ),
        pytest.param(
            {"app/services/user.py": "import app.services.task\n", "app/services/task.py": ""},
            "Service layers: services call lower layers only",
            id="lower-service-imports-higher",
        ),
        pytest.param(
            {"app/services/project.py": "import app.services.phase\n", "app/services/phase.py": ""},
            "Service layers: services call lower layers only",
            id="same-layer-services-import-each-other",
        ),
        pytest.param(
            {
                "app/services/user.py": "import app.jobs.widget\n",
                "app/jobs/widget.py": "import app.services.task\n",
                "app/services/task.py": "",
            },
            "Service layers: services call lower layers only",
            id="lower-service-reaches-higher-through-jobs",
        ),
    ],
)
def test_violation_breaks_contract(
    tmp_path: Path, files: dict[str, str], broken_contract: str
) -> None:
    result = lint_copy(tmp_path, files)

    assert result.returncode != 0
    assert f"{broken_contract} BROKEN" in result.stdout


def test_rules_may_import_pure_core_modules(tmp_path: Path) -> None:
    result = lint_copy(
        tmp_path,
        {"app/core/text.py": "import re\n", "app/rules/widget.py": "import app.core.text\n"},
    )

    assert result.returncode == 0, result.stdout


def test_services_may_call_lower_layers(tmp_path: Path) -> None:
    result = lint_copy(
        tmp_path,
        {
            "app/services/requirement.py": (
                "import app.services.approval\nimport app.services.task\n"
            ),
            "app/services/task.py": "import app.services.numbering\n",
            "app/services/numbering.py": "",
            "app/services/approval.py": "",
        },
    )

    assert result.returncode == 0, result.stdout
