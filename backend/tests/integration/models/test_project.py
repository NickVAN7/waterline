"""`project` and `project_membership` constraints and defaults (schema-doc; design-doc §3,
§3.1)."""

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import ProjectRole, ProjectStatus
from app.models.project import Project
from tests.factories.org import OrganizationFactory
from tests.factories.project import ProjectFactory, ProjectMembershipFactory
from tests.factories.user import UserFactory
from tests.factories.workspace import WorkspaceFactory

pytestmark = pytest.mark.anyio


# --- Keys and the org/workspace link ---------------------------------------------------------


async def test_project_key_is_unique_within_the_workspace_across_orgs(
    session: AsyncSession,
) -> None:
    workspace = await WorkspaceFactory.create_async()
    await ProjectFactory.create_async(
        organization=await OrganizationFactory.create_async(workspace=workspace), key="PMT"
    )
    other_org = await OrganizationFactory.create_async(workspace=workspace)

    with pytest.raises(IntegrityError, match="uq_project_workspace_id_key"):
        await ProjectFactory.create_async(organization=other_org, key="PMT")


async def test_project_key_can_repeat_in_another_workspace(session: AsyncSession) -> None:
    await ProjectFactory.create_async(key="PMT")
    await ProjectFactory.create_async(key="PMT")

    count = await session.scalar(text("SELECT count(*) FROM project WHERE key = 'PMT'"))
    assert count == 2


async def test_project_takes_its_orgs_workspace(session: AsyncSession) -> None:
    org = await OrganizationFactory.create_async()

    project = await ProjectFactory.create_async(organization=org)

    stored = await session.scalar(select(Project.workspace_id).where(Project.id == project.id))
    assert stored == org.workspace_id


async def test_project_workspace_must_be_its_orgs_workspace(session: AsyncSession) -> None:
    project = await ProjectFactory.create_async()
    other_workspace = await WorkspaceFactory.create_async()

    with pytest.raises(IntegrityError, match="fk_project_organization_id_organization"):
        await session.execute(
            text("UPDATE project SET workspace_id = :workspace WHERE id = :id"),
            {"workspace": other_workspace.id, "id": project.id},
        )


# --- Modules and classification ------------------------------------------------------------------


@pytest.mark.parametrize("modules", [[], ["sprints"], ["sprints", "github"]])
async def test_v1_modules_are_allowed(session: AsyncSession, modules: list[str]) -> None:
    project = await ProjectFactory.create_async(enabled_modules=modules)

    stored = await session.scalar(select(Project.enabled_modules).where(Project.id == project.id))
    assert stored == modules


@pytest.mark.parametrize("module", ["raid", "budget", "Sprints"])
async def test_modules_outside_the_allowed_list_are_rejected(
    session: AsyncSession, module: str
) -> None:
    with pytest.raises(IntegrityError, match="ck_project_enabled_modules"):
        await ProjectFactory.create_async(enabled_modules=["sprints", module])


async def test_project_allows_every_classification_category(session: AsyncSession) -> None:
    categories = ["financial", "proprietary", "pii", "export_controlled"]
    project = await ProjectFactory.create_async(classification_categories=categories)

    stored = await session.scalar(
        select(Project.classification_categories).where(Project.id == project.id)
    )
    assert stored == categories


async def test_unknown_classification_category_is_rejected(session: AsyncSession) -> None:
    with pytest.raises(IntegrityError, match="ck_project_classification_categories"):
        await ProjectFactory.create_async(classification_categories=["pii", "secret"])


async def test_new_project_is_planning_and_unclassified_by_default(session: AsyncSession) -> None:
    org = await OrganizationFactory.create_async()
    await session.execute(
        text(
            "INSERT INTO project (id, organization_id, workspace_id, key, name, type,"
            " enabled_modules) VALUES (gen_random_uuid(), :org, :workspace, 'PMT', 'Portal',"
            " 'software', '{}')"
        ),
        {"org": org.id, "workspace": org.workspace_id},
    )

    row = (
        await session.execute(
            select(
                Project.status,
                Project.classification_level,
                Project.classification_categories,
                Project.lead_id,
                Project.archived_at,
            )
        )
    ).one()
    assert tuple(row) == (ProjectStatus.PLANNING, None, [], None, None)


@pytest.mark.parametrize(
    ("update", "constraint"),
    [
        ("UPDATE project SET type = 'hardware' WHERE id = :id", "ck_project_type"),
        ("UPDATE project SET status = 'archived' WHERE id = :id", "ck_project_status"),
        (
            "UPDATE project SET classification_level = 'secret' WHERE id = :id",
            "ck_project_classification_level",
        ),
    ],
)
async def test_project_enum_value_outside_the_enum_is_rejected(
    session: AsyncSession, update: str, constraint: str
) -> None:
    project = await ProjectFactory.create_async()

    with pytest.raises(IntegrityError, match=constraint):
        await session.execute(text(update), {"id": project.id})


# --- Project membership ---------------------------------------------------------------------------


async def test_user_holds_one_membership_per_project(session: AsyncSession) -> None:
    project = await ProjectFactory.create_async()
    user = await UserFactory.create_async()
    await ProjectMembershipFactory.create_async(project=project, user=user, role=ProjectRole.VIEWER)

    with pytest.raises(IntegrityError, match="uq_project_membership_project_id_user_id"):
        await ProjectMembershipFactory.create_async(
            project=project, user=user, role=ProjectRole.ADMIN
        )


async def test_project_role_outside_the_enum_is_rejected(session: AsyncSession) -> None:
    membership = await ProjectMembershipFactory.create_async()

    with pytest.raises(IntegrityError, match="ck_project_membership_role"):
        await session.execute(
            text("UPDATE project_membership SET role = 'owner' WHERE id = :id"),
            {"id": membership.id},
        )
