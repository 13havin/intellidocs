from sqlalchemy.orm import Session
from app.models.workspaces import Workspace
from app.models.workspace_members import WorkspaceMember

def create_workspace(db: Session, name: str, creator_id: int) -> Workspace:
    try:
        db_workspace = Workspace(name=name)
        db.add(db_workspace)
        db.flush()
        
        membership = WorkspaceMember(
            workspace_id=db_workspace.id,
            user_id=creator_id,
            role="owner"
        )
        db.add(membership)
        
        db.commit()
    except Exception:
        db.rollback()
        raise
    
    db.refresh(db_workspace)
    return db_workspace

def list_workspaces(db: Session, user_id: int) -> list[Workspace]:
    return(
        db.query(Workspace)
        .join(WorkspaceMember)
        .filter(WorkspaceMember.user_id == user_id)
        .all()   
    )
    
def get_workspace_by_id(db: Session, workspace_id: int, user_id: int) -> Workspace | None:
    return (
        db.query(Workspace)
        .join(WorkspaceMember)
        .filter(Workspace.id == workspace_id, WorkspaceMember.user_id == user_id)
        .first()
    )