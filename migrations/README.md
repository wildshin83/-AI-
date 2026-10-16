# 데이터베이스 마이그레이션

마이그레이션은 Alembic으로 관리한다. 도메인 모델이 추가되면 아래 흐름을 사용한다.

```powershell
alembic revision --autogenerate -m "add project tables"
alembic upgrade head
```

개발·배포 환경에서 데이터 모델을 임의로 다시 생성하지 않는다. 모든 스키마 변경은
마이그레이션 파일로 추적한다.
