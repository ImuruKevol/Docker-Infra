# 186. 서비스 상세 탭 카드와 헤더 디자인 통일

- 날짜: 2026-05-14
- 리뷰 ID: ghxpqajugfrlqrjxloneuulhyoeisyyv
- 요청자: 권태욱

## 사용자 원문

구성 탭과 로그 탭의 디자인과 똑같이 다른 탭들의 디자인을 통일시켜줘. 주로 헤더 부분이 중복되었거나 헤더의 디자인이 달라. 버전 이력 탭은 컨텐츠 영역의 디자인(레이아웃)도 다르고.

## 변경 파일

- `src/app/page.services/view.pug`
- `devlog.md`
- `devlog/2026-05-14/186-service-detail-tab-design-unification.md`

## 변경 내용

- Compose/Nginx 탭을 구성/로그 탭과 같은 `p-4` 내부 단일 카드 구조로 맞추고, 저장 버튼을 카드 헤더 액션으로 이동했다.
- Compose/Nginx 탭의 선택된 설정 정보는 카드 본문 툴바 행으로 정리해 상단 헤더와 역할이 겹치지 않게 했다.
- 서비스 파일 탭은 파일 트리 컴포넌트 자체 카드만 남기고 외부 헤더를 제거해 헤더 중복을 없앴다.
- 버전 이력 탭을 구성/로그 탭과 같은 카드 구조로 감싸고, 각 버전 행을 로그 행과 같은 좌우 정렬 레이아웃으로 맞췄다.

## 확인 결과

- `/opt/conda/envs/docker-infra/bin/python -m py_compile project/main/src/app/page.services/api.py project/main/src/model/struct/services_runtime.py project/main/src/model/struct/services_rollback.py`
- `wiz_project_build(projectName="main", clean=false)`
- 두 확인 모두 성공했다.

## 남은 리스크

- 실제 서비스 데이터의 파일 트리 버튼 수, 버전 설명 길이, 모바일 폭에서의 줄바꿈은 브라우저에서 추가 확인이 필요하다.
