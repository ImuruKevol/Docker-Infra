# 서비스 상세 컨테이너 버전 배지 추가

- **ID**: 017
- **날짜**: 2026-06-22
- **유형**: 기능 추가

## 작업 요약
서비스 상세의 구성 탭 컨테이너 카드에서 컨테이너명 옆 노출 상태 배지 왼쪽에 실행 이미지 버전 배지를 추가했다.
컨테이너 이미지 ref에서 tag, digest, 이미지 ID를 표시용 버전명으로 정리하고 전체 이미지 ref는 title로 확인할 수 있게 했다.

## 원문 요청사항
```text
# ReviewOps Codex 작업 요청

아래 요청을 현재 프로젝트 루트에서 처리하세요. 필요한 파일을 직접 수정하고, 마지막 응답은 한국어로 간결하게 작성하세요.
스트리밍 응답은 사용하지 않습니다. 작업이 끝난 뒤 변경 요약, 확인한 내용, 남은 리스크만 정리하세요.
이 작업의 세션 단위는 아래 리뷰 ID입니다. 리뷰 ID가 같으면 같은 Codex 히스토리 맥락으로 이어서 처리하세요.

## 사용자 요청

작업 시작

## 리뷰 요약

- 리뷰 ID: vefrcbbdewfnksgqcisqfqmaqjppjtgt
- 제목: 서비스 관리 상세
- 요청 링크: https://infra-dev.nanoha.kr/access
- Codex 요청자: 권태욱
- 프로젝트 루트: /root/docker-infra
- Codex 세션 ID: 신규
- 스크린샷 컨텍스트: 없음
- 에이전트 작업 지시서 컨텍스트: 포함됨
- HTML 문서 생성 규칙 컨텍스트: 없음
- HTML 문서 설정 컨텍스트: 없음
- HTML 프로젝트 인스트럭션 파일: 없음
- 첨부파일 컨텍스트: 0개

## 에이전트 작업 지시서

# 에이전트 작업 지시서

## 리뷰 정보

- 리뷰 ID: vefrcbbdewfnksgqcisqfqmaqjppjtgt
- 제목: 서비스 관리 상세
- 상태: in_progress
- 우선순위: normal
- 분류: ux
- 프로젝트: Docker Infra DEV
- 프로젝트 종류: web_service
- 요청 링크: https://infra-dev.nanoha.kr/access
- 화면: 1440x900
- 캡처 방식: reviewops-sdk-dom-snapshot
- 스크린샷 첨부: no
- 리뷰 첨부 파일: 0개

## 리뷰어 요청 내용

구성 탭에 컨테이너 목록에 컨테이너들이 표시되고 있는데, 각 컨테이너 이름 옆에 있는 "외부 오픈" 뱃지 부분 왼쪽에 현재 실행 중인 해당 컨테이너의 버전명도 뱃지로 보여주도록 추가해줘.
```

## 변경 파일 목록
- `src/app/page.services/view.pug`: 공개/내부 컨테이너 카드의 노출 상태 배지 왼쪽에 버전 배지를 추가.
- `src/app/page.services/view.ts`: 컨테이너 이미지 ref에서 버전 표시값과 title을 만드는 helper 추가.
- `tests/api/test_services_preflight.py`: 서비스 상세 런타임 UI 계약 테스트에 버전 배지 연결 확인 추가.
- `devlog.md`, `devlog/2026-06-22/017-service-container-version-badge.md`: 작업 이력 추가.

## 검증 결과
- 성공: `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_services_preflight.ServicesPreflightStaticContractTest.test_service_detail_operator_runtime_summary_is_wired`
- 성공: `wiz_project_build(clean=false)` normal build
- 참고: `/opt/conda/envs/docker-infra/bin/python -m unittest tests/api/test_services_preflight.py` 전체 실행은 기존 서비스 생성 템플릿 계약 기대값(`selectedTemplateReadme()`, `변수 {{editableTemplateFields().length}}개`) 불일치로 실패했다.
