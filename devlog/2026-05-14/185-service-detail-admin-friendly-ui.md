# 185. 서비스 상세 구성 탭 관리자 친화 UI 정리

- 날짜: 2026-05-14
- 리뷰 ID: ghxpqajugfrlqrjxloneuulhyoeisyyv
- 요청자: 권태욱

## 사용자 원문

구성 탭은 지금 너무 개발자틱한 스타일로 되어있어. 굳이 안보여줘도 되는 sha256값같은것도 삭제하고, 개별 액션 버튼들은 컨텍스트메뉴같은걸로 숨겨놓던가 해줘. 그리고 실행 상태 바로 아래의 카드 4개는 삭제하고.
"접속 주소나 외부 포트로 관리자와 사용자가 접근할 수 있습니다. 서비스 구성요소가 실행 중입니다." 이런 설명들은 삭제해줘. 세부 ID 부분도 삭제하고. 디자인을 더 예쁘게 수정해줘.

Compose/Nginx 탭에서는 카드형 디자인이 쓸데없이 중첩해서 들어가있어. 한 단계 제거해줘. 서비스 파일도 마찬가지야.

버전 이력에서는 버전별 설명이 너무 길어지면 레이아웃이 깨지는 문제가 있어.

## 변경 파일

- `src/app/page.services/view.pug`
- `src/app/page.services/view.ts`
- `devlog.md`
- `devlog/2026-05-14/185-service-detail-admin-friendly-ui.md`

## 변경 내용

- 구성 탭 실행 상태에서 요약 카드 4개, 컨테이너 이미지/SHA 노출, 세부 ID, 장문 상태 설명을 제거했다.
- 외부 오픈 컨테이너와 내부 전용 컨테이너 카드를 간결한 목록형 카드로 정리하고, 개별 실행/재시작/중지/삭제 액션을 더보기 메뉴로 숨겼다.
- Compose/Nginx와 서비스 파일 탭의 중첩 카드 레이어를 제거해 탭 본문 구조를 단순화했다.
- 버전 이력 설명이 길어도 두 줄 안에서 줄바꿈/말줄임 처리되도록 레이아웃을 보정했다.
- 더 이상 사용하지 않는 컨테이너 설명용 TS 헬퍼를 제거했다.

## 확인 결과

- `/opt/conda/envs/docker-infra/bin/python -m py_compile project/main/src/app/page.services/api.py project/main/src/model/struct/services_runtime.py project/main/src/model/struct/services_rollback.py`
- `wiz_project_build(projectName="main", clean=false)`
- 두 확인 모두 성공했다.

## 남은 리스크

- 실제 운영 데이터의 컨테이너 이름, 포트 라벨, 버전 설명 길이는 다양하므로 배포 후 브라우저에서 구성/서비스 파일/버전 이력 탭의 시각 확인이 필요하다.
