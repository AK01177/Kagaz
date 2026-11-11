"""
CRUD operations for User and UserProviderMapping models.
"""
from typing import Optional
from sqlalchemy.orm import Session

try:
    from app.models.user import User, UserProviderMapping
    from app.schemas.user import UserCreate, UserProviderMappingCreate
    from services.password import hash_password
except ImportError:
    from backend.app.models.user import User, UserProviderMapping
    from backend.app.schemas.user import UserCreate, UserProviderMappingCreate
    from backend.services.password import hash_password


def create_user(db: Session, data: UserCreate) -> User:
    """Create and persist a new User."""
    user_dict = data.model_dump(exclude_unset=True)
    raw_password = user_dict.pop("password", None)
    if raw_password is not None:
        user_dict["password_hash"] = hash_password(raw_password)
    if "email" in user_dict:
        user_dict["email"] = user_dict["email"].strip().lower()
    user = User(**user_dict)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_user(db: Session, user_id: str) -> Optional[User]:
    """Retrieve a User by primary key ID."""
    return db.query(User).filter(User.id == user_id).first()


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """Retrieve a User by email address."""
    return db.query(User).filter(User.email == email.strip().lower()).first()


def get_user_by_provider_subject(db: Session, provider: str, provider_subject: str) -> Optional[User]:
    """Retrieve a User by provider and provider subject ID."""
    # First check direct user column
    user = (
        db.query(User)
        .filter(User.provider == provider, User.provider_subject == provider_subject)
        .first()
    )
    if user:
        return user
    # Next check explicit mapping table
    mapping = (
        db.query(UserProviderMapping)
        .filter(UserProviderMapping.provider == provider, UserProviderMapping.provider_subject == provider_subject)
        .first()
    )
    if mapping:
        return db.query(User).filter(User.id == mapping.user_id).first()
    return None


def create_user_provider_mapping(db: Session, data: UserProviderMappingCreate) -> UserProviderMapping:
    """Create and persist an explicit external provider mapping."""
    mapping = UserProviderMapping(**data.model_dump(exclude_unset=True))
    db.add(mapping)
    db.commit()
    db.refresh(mapping)
    return mapping

