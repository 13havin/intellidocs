from fastapi import FastAPI
from app.core import config
from app.routers import health, info, users, auth, workspaces, workspace_members

from app.services.exceptions import (
    NotFoundError, UserNotMemberError, NotOwnerError, OwnershipRuleViolationError
)
from app.exception_handlers import (
    not_owner_handler, ownership_rule_violation_handler, user_not_a_member_handler, workspace_not_found_handler
)

config.validate_env_vars()

app = FastAPI(
    title="IntelliDocs API",
    version="0.1.0"
)

app.include_router(health.router)
app.include_router(info.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(workspaces.router)
app.include_router(workspace_members.router)

app.add_exception_handler(NotFoundError, workspace_not_found_handler)
app.add_exception_handler(NotOwnerError, not_owner_handler)
app.add_exception_handler(UserNotMemberError, user_not_a_member_handler)
app.add_exception_handler(OwnershipRuleViolationError, ownership_rule_violation_handler)
