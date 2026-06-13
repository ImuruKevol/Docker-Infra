# 매크로 실행 인자 사용 옵션 복원

- **ID**: 001
- **날짜**: 2026-06-13
- **유형**: UI 기능 복원

## 작업 요약
통합 매크로 화면의 실행 영역에 `실행 인자 사용` 체크박스와 인자 입력 필드를 다시 추가했습니다.
체크박스가 켜져 있을 때만 입력한 인자를 매크로 실행 API로 전달하고, 꺼져 있으면 기존처럼 빈 인자로 실행되도록 했습니다.

## 원문 요청사항
```text
매크로 실행 기능에 원래 있던 인자를 추가할지 말지 하는 기능이 없어졌어.
```

## 변경 파일 목록
- `src/app/page.macros/view.pug`
  - 매크로 실행 대상 선택 영역 아래에 `실행 인자 사용` 체크박스와 조건부 인자 입력 필드를 추가했습니다.
- `src/app/page.macros/view.ts`
  - `macroArgsEnabled`, `macroArgsInput` 상태를 추가했습니다.
  - 화면 실행 시 체크박스 상태에 따라 인자 전달 여부를 결정하도록 했습니다.
  - AI Agent에서 인자를 넘겨 실행하는 기존 경로는 명시 인자를 계속 전달하도록 보존했습니다.
- `tests/api/test_server_macros.py`
  - 매크로 화면에 실행 인자 옵션 계약이 포함되는지 정적 테스트를 보강했습니다.
- `devlog.md`
  - 이번 작업 요약 행을 추가했습니다.
- `devlog/2026-06-13/001-macro-run-args-option-restore.md`
  - 작업 상세 이력을 추가했습니다.

## 확인 결과
- 성공: `/opt/conda/envs/docker-infra/bin/python -m py_compile project/main/src/app/page.macros/api.py`
- 성공: `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_server_macros.ServerMacrosStaticContractTest`
- 성공: `wiz_project_build(projectName="main", clean=false)`
- 성공: `season-wiz-project=main`, `season-wiz-devmode=true` 쿠키 포함 `https://infra-dev.nanoha.kr/macros` HEAD 요청 200 확인
