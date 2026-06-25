# 016 매크로 스케줄 이력 일자 그룹화와 결과 탭/페이지네이션 적용

## 요청

- Review ID: `rijqcaznagxdnefmalocrkzxhtwywyzu`
- 제목: 매크로 스케줄 모달 개선

```text
작업 시작.
실행 이력이 각 서버/서비스마다 한줄씩을 차지하고 있는데, 해당 실행 이력이 같은 날에 실행이 된거면 한 이력으로 묶어줘. 그리고 나서 그 이력을 누르면 실행 결과 모달에 각 서버/서비스를 토글 버튼? 탭?으로 해서 확인할 수 있게 해줘.
실행 이력 표시 공간의 width를 조금 더 늘려줘. 그리고 최근 10건만 표시하지 말고 페이지네이션을 추가해줘.
번외로 매크로 실행 시 출력값이 길어지면 출력 표시 부분에 스크롤이 생기는데, 출력을 받아오면 항상 스크롤을 맨 아래로 내리는 편의 기능을 추가해줘.
```

## 변경 파일

- `src/model/struct/macro_schedules.py`
  - 스케줄 실행 이력을 `Asia/Seoul` 기준 실행일로 그룹화하는 `history` 조회를 추가했다.
  - 그룹 단위 pagination과 그룹 상태 요약을 반환하도록 했다.
- `src/model/struct/macros.py`
  - 매크로 매니저에서 스케줄 이력 조회 API를 노출했다.
- `src/app/page.macros/api.py`
  - `schedule_history` API를 추가했다.
- `src/app/page.macros/view.ts`
  - 스케줄 이력 페이지 로딩, pagination 상태, 일자 그룹 라벨, 결과 모달 내 대상 탭 선택을 추가했다.
  - 매크로 실행 로그 렌더링 후 출력 영역을 항상 하단으로 스크롤하도록 했다.
- `src/app/page.macros/view.pug`
  - 스케줄 모달 폭과 이력 패널 폭을 넓혔다.
  - 이력 목록을 일자 그룹 기준으로 표시하고 pagination을 추가했다.
  - 실행 결과 모달에 서버/서비스별 탭을 추가했다.
- `tests/api/test_server_macros.py`
  - 스케줄 이력 pagination, 결과 탭, 실행 로그 자동 스크롤 계약 검사를 추가했다.

## 검증

- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_server_macros.ServerMacrosStaticContractTest` 통과
- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/app/page.macros/api.py src/model/struct/macros.py src/model/struct/macro_schedules.py` 통과
- WIZ 프로젝트 빌드 통과: `wiz_project_build(projectName="main", clean=false)`
- devmode 쿠키를 포함한 접근 확인:
  - `https://infra-dev.nanoha.kr/access` HTTP 200
  - `https://infra-dev.nanoha.kr/macros` HTTP 200

## 남은 리스크

- 인증된 실제 데이터가 있는 브라우저에서 다중 서버/서비스 스케줄 이력 탭 전환은 직접 시각 검증하지 못했다.
