"""Requirements (design-doc §6; build plan, "Requirements")."""

from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.change_log import log_change
from app.authz.authorize import allowed_actions
from app.authz.context import AuthzContext
from app.authz.target import Target, project_target
from app.core.errors import NotFoundError, ValidationFailedError
from app.enums import (
    CONTENT_ITEM_CATEGORIES,
    ActivityAction,
    ActivityEntityType,
    NumberPrefix,
    RestrictionCategory,
)
from app.models.project import Project
from app.models.requirement import Requirement, RequirementRevision
from app.models.user import User
from app.repositories.project import ProjectRepository
from app.repositories.requirement import RequirementRepository
from app.rules.rank import rank_between
from app.schemas.requirement import (
    RequirementCreate,
    RequirementItem,
    RequirementRead,
    RequirementTree,
)
from app.services.numbering import NumberingService
from app.services.user import required_error

type RequirementEntity = Requirement

# The ranked-view cap (DL-159; build plan, "API conventions").
TREE_CAP = 2_000


def _categories(requirement: Requirement) -> list[RestrictionCategory]:
    return [RestrictionCategory(c) for c in requirement.restriction_categories]


class RequirementService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = RequirementRepository(session)

    async def load(self, key: str, number: int) -> tuple[Requirement, Target] | None:
        """The requirement `number` in project `key`, as a target inside its project."""
        project = await ProjectRepository(self.session).get_by_key(key)
        if project is None:
            return None
        requirement = await self.repository.get_by_number(project.id, number)
        return None if requirement is None else (requirement, project_target(project, requirement))

    async def create(
        self, ctx: AuthzContext, project: Project, values: RequirementCreate
    ) -> RequirementRead:
        """A new requirement in `project`: the next `RQ` number, `draft`, reported by the
        caller, at the bottom of its siblings, with revision 1 (design-doc §6, §6.1). 404 for a
        `parent_id` outside the project; 422 on `title` (`missing`) and on
        `restriction_categories` (`project_only`)."""
        problems = required_error(values.title, field="title")
        if problems:
            raise ValidationFailedError(problems)
        categories = frozenset(values.restriction_categories)
        if not categories <= set(CONTENT_ITEM_CATEGORIES):
            raise ValidationFailedError.on(
                ("body", "restriction_categories"),
                "Export control is set on the project, not on a requirement.",
                "project_only",
            )
        # Checked before a number is taken; another project's requirement is a 404 (S2-plan,
        # threat model).
        if values.parent_id is not None and (
            await self.repository.get_in_project(project.id, values.parent_id) is None
        ):
            raise NotFoundError
        title = values.title.strip()
        requirement = Requirement(
            project_id=project.id,
            number=await NumberingService(self.session).allocate_number(
                project, NumberPrefix.REQUIREMENT
            ),
            parent_requirement_id=values.parent_id,
            reporter_id=ctx.user_id,
            title=title,
            description_md=values.description_md,
            priority=values.priority,
            rank=rank_between(
                await self.repository.last_sibling_rank(project.id, values.parent_id), None
            ),
            restriction_level=values.restriction_level,
            restriction_categories=sorted(categories),
        )
        self.session.add(requirement)
        # The foreign keys are circular: the requirement goes in first, then revision 1.
        await self.session.flush()
        revision = RequirementRevision(
            requirement_id=requirement.id,
            revision_number=1,
            title=title,
            description_md=values.description_md,
            created_by=ctx.user_id,
        )
        self.session.add(revision)
        await self.session.flush()
        requirement.current_revision_id = revision.id
        await self.session.flush()
        log_change(
            self.session,
            project_id=project.id,
            entity_type=ActivityEntityType.REQUIREMENT,
            entity_id=requirement.id,
            action=ActivityAction.CREATED,
            changed_by=ctx.user_id,
        )
        return await self.read(ctx, requirement)

    async def tree(self, project: Project) -> RequirementTree:
        """The project's requirements for the tree, up to the cap (DL-159)."""
        rows = await self.repository.ranked(project.id, TREE_CAP + 1)
        return RequirementTree(
            items=[
                RequirementItem(
                    id=r.id,
                    number=r.number,
                    parent_id=r.parent_requirement_id,
                    title=r.title,
                    status=r.status,
                    priority=r.priority,
                    restriction_level=r.restriction_level,
                    restriction_categories=_categories(r),
                    current_revision_id=r.current_revision_id,
                    approved_revision_id=r.approved_revision_id,
                )
                for r in rows[:TREE_CAP]
            ],
            truncated=len(rows) > TREE_CAP,
        )

    async def read(self, ctx: AuthzContext, requirement: Requirement) -> RequirementRead:
        """The requirement, with the actions the caller may take on it."""
        # Foreign keys, so never None; the project is the loader's, an identity-map hit.
        project = cast(Project, await self.session.get(Project, requirement.project_id))
        reporter = cast(User, await self.session.get(User, requirement.reporter_id))
        return RequirementRead(
            id=requirement.id,
            number=requirement.number,
            parent_id=requirement.parent_requirement_id,
            title=requirement.title,
            description_md=requirement.description_md,
            status=requirement.status,
            priority=requirement.priority,
            reporter_id=requirement.reporter_id,
            reporter_name=reporter.name,
            restriction_level=requirement.restriction_level,
            restriction_categories=_categories(requirement),
            current_revision_id=requirement.current_revision_id,
            approved_revision_id=requirement.approved_revision_id,
            approved_at=requirement.approved_at,
            version=requirement.version,
            created_at=requirement.created_at,
            updated_at=requirement.updated_at,
            allowed_actions=allowed_actions(ctx, project_target(project, requirement)),
        )
