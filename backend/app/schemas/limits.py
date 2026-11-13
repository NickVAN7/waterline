"""Length limits on request fields (DL-143; schema-doc), enforced with `Field(max_length=...)`."""

from app.core.lists import MAX_LIMIT

NAME_MAX = 100
PROJECT_DESCRIPTION_MAX = 2_000
REQUIREMENT_TITLE_MAX = 200
REQUIREMENT_DESCRIPTION_MAX = 20_000
CHANGE_NOTE_MAX = 500
APPROVAL_NOTE_MAX = 2_000
# A request's approvers (DL-226).
APPROVERS_MAX = 50
# The projects an org add may also add the person to (Q12g, DL-379): the step's list's page,
# the list cap (`MAX_LIMIT`), so the add takes all the step can show.
MEMBER_PROJECTS_MAX = MAX_LIMIT
