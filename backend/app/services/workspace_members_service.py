from sqlalchemy.orm import Session
from app.models.workspaces import Workspace
from app.models.workspace_members import WorkspaceMember
from app.schemas.workspace_members import RoleEnum
from app.services.exceptions import ExistingMemberError, NotFoundError, NotOwnerError, UserNotFoundError
from app.models.user import User

def list_workspace_members(db: Session, workspace_id: int, user_id: int) -> list[WorkspaceMember]:
    
    try:
        membership = get_workspace_member(db, workspace_id, user_id)
        if not membership:
            raise NotFoundError(f"User {user_id} is not a member of workspace {workspace_id}")
    except Exception:
        raise
    return (
        db.query(WorkspaceMember)
        .join(Workspace)
        .filter(
            WorkspaceMember.workspace_id == workspace_id,
        )
        .all()
    )

def get_workspace_member(db: Session, workspace_id: int, user_id: int) -> WorkspaceMember | None:
    return (
        db.query(WorkspaceMember)
        .filter(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id
        )
        .first()
    )
    
def add_workspace_member(db: Session, workspace_id: int, email: str, role: RoleEnum, current_user_id: int) -> WorkspaceMember:
    
    try:
        membership = get_workspace_member(db, workspace_id, current_user_id)
        if not membership or membership.role != RoleEnum.owner:
            raise NotOwnerError()
        user = db.query(User).filter(User.email == email).first()
        if not user:
            raise UserNotFoundError()
        existing_member = get_workspace_member(db, workspace_id, user.id)
        if existing_member:
            raise ExistingMemberError()
    except Exception:
        db.rollback()
        raise
    new_member = WorkspaceMember(
        workspace_id=workspace_id,
        user_id=user.id,
        role=role
    )
    db.add(new_member)
    db.commit()
    db.refresh(new_member)
    return new_member