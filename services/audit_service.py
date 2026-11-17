import json

from flask import session

from database.db import db
from models.audit import AuditLog


def record_audit(action, entity_type, entity_id=None, **details):
    db.session.add(
        AuditLog(
            user_id=session.get("user_id"),
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=json.dumps(details, default=str) if details else None,
        )
    )
