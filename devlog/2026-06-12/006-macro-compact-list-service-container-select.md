# 매크로 목록 압축과 서비스-컨테이너 선택 분리

- **ID**: 006
- **날짜**: 2026-06-12
- **유형**: UI 개선

## 작업 요약
매크로 목록 행을 매크로 이름과 첨부파일 개수 뱃지만 보이도록 줄이고, 페이지당 표시 개수를 10개로 변경했습니다.
서비스 실행 대상 선택은 서비스 선택 select와 해당 서비스의 실행 중 컨테이너 선택 select로 분리했으며, 컨테이너 표시는 런타임 서비스명 기반의 읽기 쉬운 이름을 우선 사용하도록 보정했습니다.

## 원문 요청사항
```text
매크로 목록에는 매크로 이름과 첨부파일 갯수 뱃지만 남기고 전부 삭제해줘. 여백도 컴팩트하게 줄여줘.
페이지당 20개에서 10개씩으로 줄여줘.
서비스 선택 시에는 custom search select를 중간에 하나 더 추가해서 서비스 목록에서 서비스를 선택할 수 있도록 해줘. 그리고 나서 마지막에 그 서비스에 떠있는 컨테이너 중 하나를 선택할 수 있게 해줘.
그리고 현재는 컨테이너 이름을 그대로 출력하고 있어서 랜덤 string같은 값들이 그대로 출력되는데, 이왕이면 알아보기 쉬운 이름으로 출력해줘.
```

## 변경 파일 목록
- `src/app/page.macros/view.pug`
  - 매크로 목록 행에서 설명/수정일을 제거하고 이름과 첨부파일 개수 뱃지만 남겼습니다.
  - 목록 패널 폭, 검색 input 높이, 행/하단 페이지 영역 여백을 축소했습니다.
  - 페이지당 표시 문구를 10개로 변경했습니다.
  - 서비스 실행 대상 UI를 `서비스 선택`과 `컨테이너 선택` custom search select 2단계로 분리했습니다.
- `src/app/page.macros/view.ts`
  - 매크로 페이지 크기를 10개로 변경했습니다.
  - 선택된 서비스 ID 상태와 서비스별 컨테이너 목록 필터링 로직을 추가했습니다.
  - 컨테이너 select 라벨은 `container_display_name`을 우선 사용하고, 원본 컨테이너명은 설명에 보조 표시하도록 했습니다.
- `src/app/page.macros/api.py`
  - 서비스 대상 목록을 실행 중 컨테이너로 제한했습니다.
  - 서비스 선택용 `service_key`, 컨테이너 원본명, 표시명 필드를 추가했습니다.
  - Docker 런타임 서비스명을 기반으로 랜덤 문자열 대신 컴포넌트명/복제 번호 형태의 컨테이너 표시명을 생성하도록 했습니다.
- `tests/api/test_server_macros.py`
  - 매크로 목록 10개 페이지 크기, 서비스-컨테이너 2단계 선택, 컨테이너 표시명 계약을 정적 테스트에 추가했습니다.
- `devlog.md`
  - 이번 작업 요약 행을 추가했습니다.
- `devlog/2026-06-12/006-macro-compact-list-service-container-select.md`
  - 작업 상세 이력을 추가했습니다.

## 확인 결과
- 성공: `/opt/conda/envs/docker-infra/bin/python -m py_compile project/main/src/app/page.macros/api.py`
- 성공: `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_server_macros.ServerMacrosStaticContractTest`
- 성공: `wiz_project_build(projectName="main", clean=false)`
- 성공: `season-wiz-project=main`, `season-wiz-devmode=true` 쿠키 포함 `https://infra-dev.nanoha.kr/macros` HEAD 요청 200 확인
- 제한: 인증 세션 없이 `https://infra-dev.nanoha.kr/wiz/api/page.macros/load`를 직접 호출하면 401이 반환되어 실제 서비스 대상 데이터 렌더링은 브라우저 로그인 세션에서 추가 확인이 필요합니다.
