# 컨테이너 버전 배지 digest 대신 태그 표시

- **ID**: 019
- **날짜**: 2026-06-22
- **유형**: 버그 수정

## 작업 요약
서비스 상세 컨테이너 버전 배지가 `@sha256` digest를 축약 표시하던 동작을 수정했다.
이미지 ref에 digest가 포함되어도 `:`와 `@` 사이의 태그명을 우선 표시하도록 변경했다.

## 원문 요청사항
```text
# ReviewOps Codex 작업 요청

아래 요청을 현재 프로젝트 루트에서 처리하세요. 필요한 파일을 직접 수정하고, 마지막 응답은 한국어로 간결하게 작성하세요.
스트리밍 응답은 사용하지 않습니다. 작업이 끝난 뒤 변경 요약, 확인한 내용, 남은 리스크만 정리하세요.
이 작업의 세션 단위는 아래 리뷰 ID입니다. 리뷰 ID가 같으면 같은 Codex 히스토리 맥락으로 이어서 처리하세요.

## 사용자 요청

태그가 현재 hash id값으로 표시되고 있는데, 이러면 안돼...
그냥 :, @ 이 두 문자로 잘라서 그 사이에 있는 버전명(태그 이름?)을 표시하면 될 것 같아.

---

이미지: registry.nanoha.kr/kwon3286/notedown-server:latest@sha256:9f6ba5bcd006c3566096eeb66d0e612ba03e35c639abbbaac56d59363653650d

## 리뷰 요약

- 리뷰 ID: vefrcbbdewfnksgqcisqfqmaqjppjtgt
- 제목: 서비스 관리 상세
- 요청 링크: https://infra-dev.nanoha.kr/access
- Codex 요청자: 권태욱
- 프로젝트 루트: /root/docker-infra
- Codex 세션 ID: 019eee59-e221-7e83-b61a-4d4a35de4441
- 스크린샷 컨텍스트: 없음
- 에이전트 작업 지시서 컨텍스트: 없음
- HTML 문서 생성 규칙 컨텍스트: 없음
- HTML 문서 설정 컨텍스트: 없음
- HTML 프로젝트 인스트럭션 파일: 없음
- 첨부파일 컨텍스트: 0개
```

## 변경 파일 목록
- `src/app/page.services/view.ts`: 컨테이너 이미지 버전 추출 시 `@` 앞 이미지 ref에서 태그를 파싱하도록 수정.
- `tests/api/test_services_preflight.py`: 컨테이너 버전 배지 파싱 계약 확인 추가.
- `devlog.md`, `devlog/2026-06-22/019-service-container-version-tag-parse.md`: 작업 이력 추가.

## 검증 결과
- 성공: `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_services_preflight.ServicesPreflightStaticContractTest.test_service_detail_operator_runtime_summary_is_wired`
- 성공: `wiz_project_build(clean=false)` normal build
