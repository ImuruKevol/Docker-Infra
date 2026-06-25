# 017 Storage bootstrap 서버 목록을 가로 배지 카드로 변경

## 요청

- Review ID: `zyqsvvysbltycxwkhsghunmhrnxytqqu`
- 제목: 스토리지 화면 개선

```text
각 서버들은 뱃지에 가까운 카드 느낌으로 해서 가로로 쭉 나열해줘.
```

## 변경 파일

- `src/app/page.storage/view.pug`
  - bootstrap 카드의 서버 목록을 세로 행 목록에서 가로 스크롤 배지 카드 목록으로 변경했다.
  - 각 서버 배지는 서버 이름, IP, OSD 슬롯 만들기 버튼만 표시하도록 유지했다.
  - 서버 배지마다 `shrink-0`을 적용해 가로로 이어지는 흐름을 유지했다.
- `tests/api/test_storage_models.py`
  - 가로 스크롤 서버 목록과 배지 카드 형태를 정적 계약에 반영했다.

## 검증

- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_storage_models` 통과
- WIZ 프로젝트 빌드 통과: `wiz_project_build(projectName="main", clean=false)`
- devmode 쿠키를 포함한 접근 확인:
  - `https://infra-dev.nanoha.kr/access` HTTP 200
  - `https://infra-dev.nanoha.kr/storage` HTTP 200

## 남은 리스크

- 실제 인증 세션에서 서버 수가 많은 상태의 가로 스크롤 체감은 브라우저로 직접 확인하지 못했다.
