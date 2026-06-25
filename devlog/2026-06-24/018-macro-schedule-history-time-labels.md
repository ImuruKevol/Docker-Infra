# 018 매크로 스케줄 이력과 결과 모달에 실행 시간 표시

## 요청

- Review ID: `rijqcaznagxdnefmalocrkzxhtwywyzu`
- 제목: 매크로 스케줄 모달 개선

```text
실행 이력 및 실행 결과 모달에 날짜만 나오는데 각각에 대한 시간도 나와야 해.
```

## 변경 파일

- `src/app/page.macros/view.ts`
  - 스케줄 이력 표시용 `scheduleHistoryDateTimeLabel`을 추가해 실행일뿐 아니라 실행 시간까지 표시하도록 했다.
- `src/app/page.macros/view.pug`
  - 실행 이력 목록과 실행 결과 모달 헤더를 날짜+시간 표시로 변경했다.
  - 결과 모달의 선택된 서버/서비스 행에도 해당 작업의 날짜+시간을 표시했다.
- `tests/api/test_server_macros.py`
  - 날짜+시간 라벨 helper가 매크로 화면 계약에 포함되도록 정적 검사를 추가했다.

## 검증

- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_server_macros.ServerMacrosStaticContractTest` 통과
- `git diff --check -- src/app/page.macros/view.ts src/app/page.macros/view.pug tests/api/test_server_macros.py` 통과
- WIZ 프로젝트 빌드 통과: `wiz_project_build(projectName="main", clean=false)`
- devmode 쿠키를 포함한 접근 확인:
  - `https://infra-dev.nanoha.kr/access` HTTP 200
  - `https://infra-dev.nanoha.kr/macros` HTTP 200

## 남은 리스크

- 실제 스케줄 이력 데이터가 있는 인증 브라우저에서 지역별 시간 포맷 표시를 직접 시각 검증하지 못했다.
