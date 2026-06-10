# DDNS 레코드 Hostname 외부 링크 아이콘 추가

- 날짜: 2026-06-08
- 작업 ID: 016
- 리뷰 ID: wmidmxmacideroaomknwjpmugxraddqf
- 프로젝트: main

## 사용자 요청

- Hostname 값 바로 오른쪽(mr-2)에 연결 서비스 컬럼과 같은 아이콘을 추가.

## 변경 파일

- `src/app/page.domains/view.pug`
- `tests/api/test_domain_management_ui.py`
- `devlog.md`
- `devlog/2026-06-08/016-ddns-hostname-external-link-icon.md`

## 작업 내용

- DDNS 레코드 Hostname 새 창 링크 내부에 `fa-arrow-up-right-from-square` 아이콘을 추가.
- Hostname 텍스트와 아이콘을 한 줄의 inline-flex로 묶고, 아이콘에 `ml-2 mr-2` 여백을 적용.
- 정적 계약 테스트에 Hostname 텍스트 span과 아이콘 클래스 확인을 추가.

## 검증 결과

- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_domain_management_ui` 통과.
- `git diff --check -- src/app/page.domains/view.pug tests/api/test_domain_management_ui.py` 통과.
- `wiz_project_build(projectName="main", clean=false)` 통과.
- 쿠키 `season-wiz-project=main; season-wiz-devmode=true`로 `https://infra-dev.nanoha.kr/domains` 200 응답 확인.

## 남은 리스크

- 로그인 세션이 없어 실제 데이터가 채워진 원격 화면은 확인하지 못했다.
