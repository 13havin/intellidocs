from fastapi import APIRouter, Depends, HTTPException
from app.schemas.workspaces import WorkspaceResponse, WorkspaceCreate
from app.dependencies import get_current_user
from app.services import workspace_service
from app.dependencies import get_db
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/v1/workspaces", tags=["workspaces"])

@router.post("/", response_model=WorkspaceResponse, status_code=201)
def create_workspace(payload: WorkspaceCreate, db:Session = Depends(get_db), current_user=Depends(get_current_user)):
    return workspace_service.create_workspace(
        db,
        payload.name,
        creator_id=current_user.id
    )

@router.get("/", response_model=list[WorkspaceResponse], status_code=200)
def list_workspaces(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    workspaces = workspace_service.list_workspaces(
        db,
        user_id=current_user.id
    )
    if not workspaces:
        raise HTTPException(status_code=404, detail="No workspaces found")
    return workspaces

@router.get("/{workspace_id}", response_model=WorkspaceResponse, status_code=200)
def get_workspace(workspace_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    workspace = workspace_service.get_workspace_by_id(
        db,
        workspace_id,
        user_id=current_user.id
    )
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return workspace