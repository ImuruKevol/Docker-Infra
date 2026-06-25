# 020 매크로 스케줄 이력 시간 표시 타임존 정규화

## 요청

- Review ID: `rijqcaznagxdnefmalocrkzxhtwywyzu`
- 제목: 매크로 스케줄 모달 개선

```text
첨부된 스크린샷을 보면 날짜/시간 표시에 하나는 타임존이 적용된 상태로 표시되고, 하나는 적용이 안된 상태로 표시되는 문제가 있어. 타임존이 적용이 된 상태로 표시가 되어야 해.
그리고 실행 이력 목록에서도 똑같아.
```

## 변경 파일

- `src/model/struct/macro_schedules.py`
  - 스케줄 이력 그룹의 `run_at`, `created_at`, `updated_at`을 timezone 포함 ISO 문자열로 반환하도록 정규화했다.
- `src/app/page.macros/view.ts`
  - timezone 없는 날짜/시간 문자열을 UTC 기준으로 해석해 브라우저 로컬 타임존으로 표시하도록 `normalizeDateInput`을 추가했다.
  - 실행 이력 목록과 결과 모달에서 동일한 날짜 formatter 경로를 사용하도록 유지했다.
- `tests/api/test_server_macros.py`
  - timezone 정규화 helper와 backend ISO 변환 helper 계약을 정적 검사에 추가했다.

## 검증

- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_server_macros.ServerMacrosStaticContractTest` 통과
- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/macro_schedules.py` 통과
- `git diff --check -- src/app/page.macros/view.ts src/model/struct/macro_schedules.py tests/api/test_server_macros.py` 통과
- WIZ 프로젝트 빌드 통과: `wiz_project_build(projectName="main", clean=false)`
- devmode 쿠키를 포함한 접근 확인:
  - `https://infra-dev.nanoha.kr/access` HTTP 200
  - `https://infra-dev.nanoha.kr/macros` HTTP 200

## 남은 리스크

- 첨부 스크린샷과 같은 실제 이력 데이터로 브라우저에서 두 timestamp가 완전히 동일하게 보이는지는 직접 재검증하지 못했다.
