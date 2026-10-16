"""도면번호·규격의 비교용 정규화 규칙.

원본 문자열은 바꾸지 않고, ERP 후보 검색과 BOM 비교에만 이 값을 사용한다.
"""

from __future__ import annotations

import re

_REVISION_SUFFIX = re.compile(r"(?:[\s._-]*(?:REV(?:ISION)?|R)\s*[._-]*[A-Z0-9]+)$", re.IGNORECASE)


def normalize_drawing_number(value: str | None) -> str:
    """공백·하이픈·접두어 차이와 끝 Rev 표기를 제거한 비교 키를 만든다."""

    if not value:
        return ""
    without_revision = _REVISION_SUFFIX.sub("", value.strip().upper())
    return "".join(character for character in without_revision if character.isalnum())


def normalize_specification(value: str | None) -> str:
    """규격 후보 검색을 위한 공백·대소문자 무시 키를 만든다."""

    if not value:
        return ""
    return "".join(character for character in value.upper() if not character.isspace())
