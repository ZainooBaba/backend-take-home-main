from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session
from typing import Optional

from app.database import SessionLocal


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def require_ranger(
    x_user_id: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """Dependency that validates the caller is a ranger. Returns the Ranger ORM object."""
    if not x_user_id:
        raise HTTPException(status_code=401, detail="X-User-ID header is required")
    from app.models import Ranger
    ranger = db.query(Ranger).filter(Ranger.id == x_user_id).first()
    if not ranger:
        raise HTTPException(status_code=403, detail="Only rangers can perform this action")
    return ranger
