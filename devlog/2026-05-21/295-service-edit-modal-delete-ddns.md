# 서비스 수정 모달 즉시 표시와 DDNS 삭제 실패 내성 보강

- **ID**: 295
- **날짜**: 2026-05-21
- **유형**: UX/안정성 개선

## 작업 요약

서비스 상세 화면에서 `수정` 버튼을 누르면 상세 원문과 도메인 옵션을 불러오기 전에 모달을 먼저 열고 내부 로딩 상태를 보여주도록 바꿨다.
`notion` 서비스 삭제 실패는 DDNS unregister 단계에서 원격 API가 HTML 응답을 반환해 삭제 전체가 중단된 것이 원인이었다. DDNS 등록 이력이 없는 도메인은 원격 삭제를 건너뛰고, 원격 DDNS 삭제 실패도 경고로 기록하되 로컬 서비스 삭제는 계속 진행하도록 보강했다.

## 원문 요청사항

```text
# ReviewOps Codex 작업 요청

아래 요청을 현재 프로젝트 루트에서 처리하세요. 필요한 파일을 직접 수정하고, 마지막 응답은 한국어로 간결하게 작성하세요.
스트리밍 응답은 사용하지 않습니다. 작업이 끝난 뒤 변경 요약, 확인한 내용, 남은 리스크만 정리하세요.
이 작업의 세션 단위는 아래 리뷰 ID입니다. 리뷰 ID가 같으면 같은 Codex 히스토리 맥락으로 이어서 처리하세요.

## 사용자 요청

다른 문제도 많네. 일단 수정 버튼을 눌렀을 때 일단 모달부터 띄우고 로딩을 띄우던가 해줘. 지금은 반응이 없다가 갑자기 뜨는 등 문제가 너무 많아. 그리고 현재 생성했떤 서비스 중 notion 서비스에 대해 서비스 삭제가 되지 않아. 확인해줘.

## 리뷰 요약

- 리뷰 ID: mlmvfhzjkgkstxxnmwfewflidojpggod
- 제목: 서비스 상세 기능 개선
- 요청 링크: https://infra-dev.nanoha.kr/services
- 프로젝트 루트: /root/docker-infra
```

## 변경 파일 목록

- `src/app/page.services/view.ts`
  - 수정 모달 요청 순번과 `editLoading` 상태를 추가했다.
  - `openEditModalAsync`가 먼저 모달을 열고 로딩을 표시한 뒤 상세 source/options를 불러오도록 순서를 변경했다.
  - 로딩 중 저장 액션을 막고, 사용자가 모달을 닫으면 늦게 도착한 응답을 무시하도록 했다.
- `src/app/page.services/view.pug`
  - 수정 모달 header와 본문에 로딩 표시/오버레이를 추가했다.
  - 로딩 중 저장/저장 후 적용 버튼을 비활성화했다.
- `src/model/struct/domains_ddns.py`
  - DDNS 등록 이력이 없는 서비스 도메인은 원격 unregister 호출 없이 `ddns_registration_not_found`로 건너뛰도록 했다.
- `src/model/struct/services_delete.py`
  - DDNS unregister 실패를 서비스 삭제 전체 실패로 전파하지 않고 warning result로 남긴 뒤 삭제를 계속 진행하도록 했다.
- `tests/api/test_services_preflight.py`
  - 수정 모달 즉시 표시와 DDNS 삭제 내성 계약을 정적 테스트에 추가했다.
- `devlog.md`
- `devlog/2026-05-21/295-service-edit-modal-delete-ddns.md`

## 확인한 내용

- DB에서 `notion` 서비스가 `draft` 상태로 남아 있고, 최근 `service.delete` operation들이 `SERVICE_DDNS_RECORD_REMOVE_FAILED`로 실패한 것을 확인했다.
- 해당 서비스 도메인 `notion.sub.nanoha.kr`에는 DDNS endpoint metadata는 있으나 DDNS registration row는 없는 것을 확인했다.
- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/services_delete.py src/model/struct/domains_ddns.py` 성공
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_services_preflight.ServicesPreflightStaticContractTest` 성공
- `wiz_project_build(projectName="main", clean=false)` 성공
- `git diff --check` 성공
- `season-wiz-project=main`, `season-wiz-devmode=true` 쿠키로 `https://infra-dev.nanoha.kr/services` HEAD 요청 200 확인
- 같은 쿠키로 `https://infra-dev.nanoha.kr/wiz/api/page.services/load` POST 요청 시 HTTP 200, WIZ 응답 `401 AUTHENTICATION_REQUIRED` 확인

## 남은 리스크

- 로그인 세션이 없어 실제 브라우저에서 수정 모달 클릭 반응과 삭제 버튼을 직접 클릭 검증하지 못했다.
- DDNS 원격 서버가 HTML을 반환하는 근본 API 경로 문제는 별도로 endpoint 설정 또는 DDNS 서버 라우트를 확인해야 한다. 이번 변경은 서비스 삭제가 그 문제 때문에 막히지 않도록 하는 내성 보강이다.
