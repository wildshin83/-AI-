"""업무 변경과 감사 기록을 함께 확정하거나 되돌린다."""

from contextlib import contextmanager

from sqlalchemy.orm import Session


@contextmanager
def commit_or_rollback(session: Session):
    try:
        yield
        session.commit()
    except Exception:
        session.rollback()
        raise
