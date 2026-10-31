"""The database sorts ranks as Python does (design-doc §6 "Manual ordering": ranks use only
digits and lowercase letters, which the `en_US.utf8` collation orders like Python's string
comparison; DL-205). A change of collation, or of the rank alphabet, fails here instead of
silently misordering items."""

import random

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.requirement import Requirement
from app.rules.rank import rank_between
from tests.factories.project import ProjectFactory
from tests.factories.requirement import RequirementFactory

pytestmark = pytest.mark.anyio


def generated_ranks() -> list[str]:
    """500 drops at seeded random places, plus a run of drops into one gap (long ranks)."""
    chooser = random.Random(205)  # noqa: S311 -- a seeded test order, not a secret
    ranks = [rank_between(None, None)]
    for _ in range(500):
        place = chooser.randint(0, len(ranks))
        before = ranks[place - 1] if place > 0 else None
        after = ranks[place] if place < len(ranks) else None
        ranks.insert(place, rank_between(before, after))
    for _ in range(60):
        ranks.insert(2, rank_between(ranks[1], ranks[2]))
    return ranks


async def test_order_by_rank_matches_pythons_order(session: AsyncSession) -> None:
    """Bug: the database's collation orders some ranks differently from Python (mixed case,
    punctuation, or a non-C collation rule), so the tree and the rank math disagree."""
    ranks = generated_ranks()
    shuffled = random.Random(5).sample(ranks, len(ranks))  # noqa: S311 -- the same
    project = await ProjectFactory.create_async()
    for number, rank in enumerate(shuffled, start=1):
        await RequirementFactory.create_async(project=project, number=number, rank=rank)

    stored = await session.scalars(
        select(Requirement.rank)
        .where(Requirement.project_id == project.id)
        .order_by(Requirement.rank)
    )

    assert list(stored) == sorted(ranks)
    assert sorted(ranks) == ranks
