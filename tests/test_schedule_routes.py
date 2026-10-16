"""일정 UI의 접근 범위·오류 안내·변경 결과."""

from datetime import date

from app.models.auth import AuthUser
from app.models.schedules import ScheduleChangeRequest
from tests.test_schedules import project as project  # noqa: F401


def test_member_requests_then_reviewer_approves(account_db, accounts, project, sign_in):
    client = sign_in(accounts[0])
    response = client.get(f"/projects/{project.id}/schedule?focus=incoming")
    assert response.status_code == 200 and "승인 요청" in response.text
    response = client.post(
        f"/projects/{project.id}/schedule",
        data={
            "target_delivery_date": "2026-12-01",
            "incoming_date": "2026-11-20",
            "fob_date": "",
            "base_version": "1",
            "reason": "고객 일정 변경",
        },
    )
    assert response.status_code == 200 and "승인 대기" in response.text
    assert project.target_delivery_date == date(2026, 11, 15)
    sign_in(accounts[1])
    assert client.get("/schedule-requests").status_code == 200
    response = client.post("/schedule-requests/1/approve", data={"comment": "확인"})
    assert response.status_code == 200 and "승인" in response.text
    assert project.target_delivery_date == date(2026, 12, 1)


def test_invalid_date_preserves_values(accounts, project, sign_in):
    client = sign_in(accounts[0])
    response = client.post(
        f"/projects/{project.id}/schedule",
        data={
            "target_delivery_date": "2026-02-30",
            "incoming_date": "2026-11-20",
            "base_version": "1",
            "reason": "유지할 사유",
        },
    )
    assert response.status_code == 422
    assert "유지할 사유" in response.text and "2026-11-20" in response.text
    assert "날짜" in response.text


def test_member_cannot_read_others_request_or_review(account_db, accounts, project, sign_in):
    other = AuthUser(email="other@example.test", display_name="other", password_hash="unused")
    account_db.add(other)
    account_db.flush()
    pending = ScheduleChangeRequest(
        project_id=project.id,
        requested_by_id=other.id,
        requested_by_name="other",
        base_version=1,
        reason="private",
        status="pending",
    )
    account_db.add(pending)
    account_db.commit()
    client = sign_in(accounts[0])
    assert client.get(f"/schedule-requests/{pending.id}").status_code == 403
    assert "private" not in client.get("/schedule-requests").text
    assert client.post(f"/schedule-requests/{pending.id}/approve").status_code == 403
    assert client.get("/schedule-requests?page=0").status_code == 422


def test_reviewer_can_directly_save_clear_date_and_view_history(accounts, project, sign_in):
    client = sign_in(accounts[1])
    response = client.post(
        f"/projects/{project.id}/schedule",
        data={
            "target_delivery_date": "",
            "incoming_date": "2028-02-29",
            "base_version": "1",
            "reason": "입고일 확정",
        },
    )
    assert response.status_code == 200 and "저장했습니다" in response.text
    assert project.target_delivery_date is None and project.incoming_date == date(2028, 2, 29)
    assert "입고일 확정" in response.text
