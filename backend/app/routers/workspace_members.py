from fastapi import APIRouter, Depends, HTTPException
from app.schemas.workspace_members import WorkspaceMemberResponse, WorkspaceMemberCreate, WorkspaceMemberUpdate
from app.dependencies import get_current_user
from app.services import workspace_members_service
from app.dependencies import get_db
from sqlalchemy.orm import Session

from app.services.exceptions import ExistingMemberError, NotFoundError, NotOwnerError, UserNotFoundError, OwnershipRuleViolationError

router = APIRouter(prefix="/api/v1/workspaces", tags=["workspace_members"])

@router.get("/{workspace_id}/members", response_model=list[WorkspaceMemberResponse], status_code=200)
def get_workspace_members(workspace_id: int, db:Session = Depends(get_db), current_user=Depends(get_current_user)):
    try:
        members = workspace_members_service.list_workspace_members(
            db,
            workspace_id,
            current_user.id
        )
        return [
            WorkspaceMemberResponse(
                email=member.user.email,
                role=member.role,
                joined_at=member.joined_at,
            )
            for member in members
        ]
    except NotFoundError:
        raise HTTPException(status_code=404, detail=f"Workspace not found")
    
@router.post("/{workspace_id}/members", response_model=WorkspaceMemberResponse, status_code=201)
def add_workspace_member(workspace_id: int, payload: WorkspaceMemberCreate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    # Check if the current user is an owner of the workspace 
    try:
        # Add the new member
        member = workspace_members_service.add_workspace_member(db, workspace_id, payload.email, payload.role, current_user.id)
        return WorkspaceMemberResponse(
            role=member.role,
            email=member.user.email,
            joined_at=member.joined_at,
        )
    except NotFoundError:
        raise HTTPException(status_code=404, detail=f"Workspace not found")
    
    except NotOwnerError:
        raise HTTPException(status_code=403, detail="You do not have permission to add members to this workspace")
    
    except UserNotFoundError:
        raise HTTPException(status_code=404, detail=f"{payload.email} is not found")
    
    except ExistingMemberError:
        raise HTTPException(status_code=409, detail=f"{payload.email} is already a member of workspace")
 

@router.patch("/{workspace_id}/members/{user_id}", response_model=WorkspaceMemberResponse, status_code=200)
def update_workspace_member_role(workspace_id: int, user_id: int, payload: WorkspaceMemberUpdate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    # Check if the current user is an owner of the workspace 
    try:
        # Add the new member
        updated_member = workspace_members_service.update_workspace_member_role(db, workspace_id, user_id, payload.role, current_user.id)
        return WorkspaceMemberResponse(
            role=updated_member.role,
            email=updated_member.user.email,
            joined_at=updated_member.joined_at,
        )
    except NotFoundError:
        raise HTTPException(status_code=404, detail=f"Workspace not found")
    
    except NotOwnerError:
        raise HTTPException(status_code=403, detail="You do not have permission to change member roles in this workspace")
    
    except UserNotFoundError:
        raise HTTPException(status_code=404, detail=f"User is not a member")
    
    except OwnershipRuleViolationError:
        raise HTTPException(status_code=409, detail=f"Cannot remove the last owner of the workspace")  
