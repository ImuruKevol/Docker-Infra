# 매크로 스케줄 결과 모달 stdout/stderr 세로 배치

## 요청

stdout과 stderr을 다단으로 표시하지 말고 그냥 아래로 내려가는 흐름으로 배치해줘. 특히 stderr은 내용이 없으면 굳이 보여주지 말고.

## 변경 내용

- 매크로 스케줄 실행 결과 모달의 stdout/stderr 영역을 2단 grid에서 세로 흐름으로 변경했다.
- stderr 출력이 없을 때는 stderr 섹션 자체가 렌더링되지 않도록 했다.
- 정적 계약 테스트에 세로 흐름과 stderr 빈 상태 문구 제거 조건을 추가했다.

## 변경 파일

- `src/app/page.macros/view.pug`
- `tests/api/test_server_macros.py`
- `devlog.md`
- `devlog/2026-06-23/009-macro-schedule-result-stream-layout.md`

## 확인 결과

- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_server_macros.ServerMacrosStaticContractTest`
- WIZ build `main` 성공
- 쿠키 `season-wiz-project=main; season-wiz-devmode=true` 포함 `/api/system/health` 호출 결과 DB `schema_version` 022 확인

## 남은 리스크

- 로그인 테스트 비밀번호가 없어 실제 브라우저에서 결과 모달의 세로 배치와 stderr 숨김 동작을 수동 확인하지는 못했다.
