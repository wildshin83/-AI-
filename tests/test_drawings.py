from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import Base
from app.models.project import Project
from app.services.drawings import register_drawing_file


@pytest.fixture()
def session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as database_session:
        yield database_session


def test_register_drawing_preserves_each_revision_file(session: Session, tmp_path: Path) -> None:
    project = Project(
        project_number="DRAWING-001",
        project_name="도면 검증",
        customer_name="고객사",
        equipment_unit="1호기",
        manager_name="담당자",
        status="견적",
    )
    session.add(project)
    session.flush()
    path = tmp_path / "part_rev_a.pdf"
    path.write_bytes(b"drawing")

    drawing = register_drawing_file(
        session,
        project_id=project.id,
        bom_item=None,
        bom_revision=None,
        drawing_number="DWG-001",
        drawing_revision="A",
        file_type="pdf",
        original_file_name="part_rev_a.pdf",
        stored_path=path,
        mime_type="application/pdf",
        uploaded_by="담당자",
        memo=None,
    )

    assert drawing.id is not None
    assert drawing.drawing_revision == "A"
    assert path.read_bytes() == b"drawing"
