from fastapi import Request
from fastapi.responses import JSONResponse

from app.services.exceptions import (
    NotFoundError, UserNotMemberError, NotOwnerError, OwnershipRuleViolationError
)

async def workspace_not_found_handler(request: Request, exc: NotFoundError):
    return JSONResponse(
        status_code=404,
        content={"detail": "Workspace not found"},
    )
    
async def not_owner_handler(request: Request, exc: NotOwnerError):
    return JSONResponse(
        status_code=403,
        content={"detail": "You do not have permission to perform this action"},
    )
    
async def user_not_a_member_handler(request: Request, exc: UserNotMemberError):
    return JSONResponse(
        status_code=404,
        content={"detail": "User is not a member of the workspace"},
    )
    
async def ownership_rule_violation_handler(request: Request, exc: OwnershipRuleViolationError):
    return JSONResponse(
        status_code=409,
        content={"detail": "Cannot remove the last owner of the workspace"},
    )