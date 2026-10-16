"""번들 참고자료의 경로가 작업 폴더 이동 후에도 유지되는지 검증한다."""

from app.config import reference_material_path


def test_customer_quote_template_is_loaded_from_reference_materials_directory() -> None:
    template = reference_material_path("SINGLEX_LGES_QUOTE_FORM_V5.20_20250529_EN.xlsx")

    assert template.parent.name == "참고자료"
    assert template.is_file()
