from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError
from app.models.workspaces import Workspace
from app.models.workspace_members import WorkspaceMember
from app.schemas.workspace_members import RoleEnum
from app.services.exceptions import ExistingMemberError, NotFoundError, NotOwnerError, UserNotFoundError, OwnershipRuleViolationError
from app.models.user import User

def list_workspace_members(db: Session, workspace_id: int, user_id: int) -> list[WorkspaceMember]:
    if get_workspace_member(db, workspace_id, user_id) is None:
        raise NotFoundError()

    return (
        db.query(WorkspaceMember)
        .options(joinedload(WorkspaceMember.user))
        .filter(WorkspaceMember.workspace_id == workspace_id)
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
        workspace = (
            db.query(Workspace)
            .filter(Workspace.id == workspace_id)
            .with_for_update()
            .first()
        )
        if workspace is None:
            raise NotFoundError()
        
        membership = get_workspace_member(db, workspace_id, current_user_id)
        if not membership:
            raise NotFoundError()
        
        if membership.role != RoleEnum.owner:
            raise NotOwnerError()
        
        user = db.query(User).filter(User.email == email).first()
        if not user:
            raise UserNotFoundError()
        
        existing_member = get_workspace_member(db, workspace_id, user.id)
        if existing_member:
            raise ExistingMemberError()
        
        new_member = WorkspaceMember(
            workspace_id=workspace_id,
            user_id=user.id,
            role=role
        )
        db.add(new_member)
        db.commit()
    
    except IntegrityError as exc:
        db.rollback()
        
        original = exc.orig
        diagnostics = getattr(original, "diag", None)
        
        if (
            getattr(original, "pgcode", None) == "23505" 
            and getattr(diagnostics, "table_name", None)
            == "workspace_members"
            and getattr(diagnostics, "constraint_name", None)
            == "workspace_members_workspace_id_user_id_key"
        ):
            raise ExistingMemberError() from exc

        raise
    
    except Exception:
        db.rollback()
        raise

    db.refresh(new_member)
    return new_member

def update_workspace_member_role(db: Session, workspace_id: int, user_id: int, new_role: RoleEnum, current_user_id: int) -> WorkspaceMember:
    try:
        workspace = (
            db.query(Workspace)
            .filter(Workspace.id == workspace_id)
            .with_for_update()
            .first()
        )
        if workspace is None:
            raise NotFoundError()
        
        membership = get_workspace_member(db, workspace_id, current_user_id)
        if not membership:
            raise NotFoundError()
            
        if membership.role != RoleEnum.owner:
            raise NotOwnerError()
        
        member_to_update = get_workspace_member(db, workspace_id, user_id)
        if not member_to_update:
            raise UserNotFoundError()
        
        if (
            member_to_update.role == RoleEnum.owner
            and new_role != RoleEnum.owner
        ):
            # Check if the current user is the last owner of the workspace
            other_owner = (
                db.query(WorkspaceMember)
                .filter(
                    WorkspaceMember.workspace_id == workspace_id,
                    WorkspaceMember.role == RoleEnum.owner,
                    WorkspaceMember.user_id != member_to_update.user_id,
                )
                .first()
            )

            if other_owner is None:
                raise OwnershipRuleViolationError()
    
        member_to_update.role = new_role
        db.commit()
        
    except Exception as e:
        db.rollback()
        raise
    
    db.refresh(member_to_update)
    return member_to_update