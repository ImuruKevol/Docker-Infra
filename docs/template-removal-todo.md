# 템플릿 기능 제거 TODO

- 작성일: 2026-05-11
- 최근 갱신: 2026-05-11
- 대상 화면: `/services`, `/services/create`, 기존 `/templates`
- 목적: 템플릿/기본 구성이라는 별도 제품 개념을 제거하고, 서비스 생성은 `AI 초안`, `Compose 직접 작성`, `기존 Compose 가져오기` 세 흐름으로 단순화한다.
- 연계 문서: `docs/docker-infra-development-todo.md`, `docs/docker-infra-remaining-todo.md`, `docs/service-management-audit-todo.md`
- 핵심 제약: 템플릿 관리의 AI 초안 생성 프롬프트, 모델 선택, 스트리밍, 자동 보정, Compose 검증 흐름은 서비스 생성으로 이전해 재사용한다.

## 현재 진행 현황

- 완료: `/services/create`를 `AI 초안`, `Compose 직접 작성`, `서버 Compose 가져오기` 흐름으로 재구성했다.
- 완료: 서비스 생성 API와 wizard에서 `template_id` 요구를 제거하고 `manual_compose`, `ai_draft`, `server_compose_import` 원본을 사용하게 했다.
- 완료: 템플릿 page/API/model/seed를 삭제하고, 사이드바와 번역에서 템플릿 메뉴를 제거했다.
- 완료: 신규 core schema에서 `templates`, `template_versions`를 제거하고 기존 DB drop migration을 추가했다.
- 완료: OpenAPI, runtime/design 문서, 관련 정적 테스트를 새 방향으로 1차 정리했다.
- 남음: 상위 TODO 문서(`development`, `remaining`, `service-management-audit`)와 README의 템플릿 기반 설명을 새 서비스 초안 흐름으로 갱신한다.
- 완료: AI/직접 작성/import 초안 metadata를 서비스 metadata와 최초 `compose_versions.metadata.draft`에 저장한다.

## 1. 결정 사항

템플릿은 사용자에게 노출되는 제품 기능에서 제거한다. 일반 사용자는 서비스 종류나 기본 구성을 먼저 관리하지 않고, 원하는 서비스를 자연어로 설명해 AI 초안을 만들거나, Docker Compose를 직접 작성하거나, 기존 서버의 Compose 파일을 가져와 서비스를 만든다.

이번 제거 작업에서 고정하는 방향은 다음과 같다.

- `/templates` 독립 화면은 제거한다.
- 사이드바, 번역, 문서, OpenAPI에서 템플릿 관리 항목을 제거한다.
- `templates`, `template_versions` DB 테이블은 최종적으로 제거한다.
- 기본 seed 템플릿과 템플릿 릴리즈/버전 관리 기능은 제거한다.
- 서비스 생성 API는 `template_id`를 요구하지 않는다.
- 서비스 생성의 입력 원본은 `ai_draft`, `manual_compose`, `server_compose_import`로 정리한다.
- AI가 생성한 README 성격의 설명은 템플릿 README가 아니라 서비스 생성 검토용 운영 메모 또는 compose version metadata로 다룬다.
- 서비스 버전 관리는 기존 `compose_versions` 중심으로 유지하고, 템플릿 버전 관리는 만들지 않는다.

## 2. 제거하지 말아야 할 것

템플릿 기능을 제거하더라도 다음은 반드시 살려서 서비스 관리로 옮긴다.

- AI 모델 선택 옵션과 시스템 설정 기반 모델 제한
- OpenAI, Gemini, Ollama 런타임 선택 정책
- SSE 스트리밍 응답과 thinking/progress 표시
- AI output JSON 계약 검증
- 실패 시 자동 재요청/보정 루프
- Compose validation 계약과 healthcheck/network/container_name 금지 규칙
- AI가 생성한 Compose 초안을 wizard form의 components로 매핑하는 로직
- generated secret 자동 생성/마스킹 정책
- AI 결과의 요약, 경고, 사용자용 설명 문구

## 3. 상태 기준

| 상태 | 의미 |
|---|---|
| Todo | 아직 구현 필요 |
| Blocked | 선행 결정 또는 마이그레이션 설계 필요 |
| Remove | 제거 또는 폐기 필요 |
| Rework | 유지하되 새 방향에 맞게 재설계 필요 |
| Verify | 구현 후 검증 필요 |

## 4. P0: 사용자 흐름 재정의

### 문제

현재 서비스 생성은 템플릿 선택을 전제로 한다. 최근 제품 방향에서는 템플릿/기본 구성 개념 자체가 일반 사용자에게 불필요한 중간 단계가 되었고, AI 초안 생성과 Compose 직접 작성만으로 생성 흐름을 충분히 설명할 수 있다.

### 완료 기준

- 새 서비스 생성 첫 화면에서 템플릿 선택 UI가 사라진다.
- 사용자는 `AI로 만들기`, `Compose 직접 작성`, `서버 Compose 가져오기` 중 하나로 시작한다.
- AI 설정이 없거나 AI 요청이 실패해도 Compose 직접 작성으로 서비스 생성이 가능하다.
- 기존 서버 Compose 가져오기 흐름은 지금처럼 `/services/create`로 이어지되 템플릿 잠금 상태를 사용하지 않는다.
- 사용자가 `template`, `기본 구성`, `서비스 종류`라는 용어를 일반 생성 흐름에서 보지 않는다.

### 작업

- [x] `/services/create` 1단계를 `서비스 초안` 중심으로 재구성한다.
- [x] 기존 `서비스 종류` 단계명과 설명을 제거한다.
- [x] `templateSelectorItems`, `selectedTemplateId`, `templateLocked`, `templateLoading` 의존을 제거한다.
- [x] AI 초안 생성 카드를 첫 번째 진입점으로 배치한다.
- [x] Compose 직접 작성/붙여넣기 패널을 AI와 같은 수준의 진입점으로 제공한다.
- [x] 서버 Compose 가져오기 완료 배너와 경고 표시는 유지하되 템플릿 선택 잠금 문구를 제거한다.
- [x] 2단계 이후의 구성 확인, 도메인, 최종 확인 흐름은 기존 서비스 wizard를 최대한 유지한다.

## 5. P0: 서비스 생성 API 계약 변경

### 문제

`services_wizard`는 일반 생성에서 `template_id` 또는 import source를 요구한다. 템플릿 기능을 제거하면 API 직접 호출도 `base_content`와 생성 원본만 검증해야 한다.

### 완료 기준

- `preflight`와 `create`는 `template_id`를 요구하지 않는다.
- `base_content` 또는 직접 작성/AI/import 결과가 없으면 사용자용 오류를 반환한다.
- 서비스 생성 결과의 `source`는 `ai_draft`, `manual_compose`, `server_compose_import` 중 하나다.
- `source_ref`에는 템플릿 ID 대신 AI 모델, 사용자가 입력한 요구사항 요약, import path, compose checksum 같은 생성 원본만 남긴다.
- 기존 서비스의 과거 `source_ref.template_id`는 마이그레이션 또는 표시 계층에서 안전하게 legacy 정보로 처리한다.

### 작업

- [x] `src/model/struct/services_wizard.py`의 `_require_template_or_import`를 `_require_base_content_source`로 재설계한다.
- [x] `SERVICE_TEMPLATE_REQUIRED`, `SERVICE_TEMPLATE_CONTENT_REQUIRED` 오류 코드를 서비스 초안 기준 오류 코드로 교체한다.
- [x] `create`의 `source_ref` fallback에서 `template_id`를 제거한다.
- [x] `preflight`, `create` 요청 payload에서 `template_id`를 제거한다.
- [x] `base_content`가 비어 있으면 `서비스 초안을 먼저 작성해주세요.` 수준의 사용자용 메시지를 반환한다.
- [x] import 흐름의 warning 허용 정책은 유지한다.
- [x] 기존 `components_from_content`는 AI/직접 작성/import Compose 모두에서 재사용한다.

## 6. P0: 템플릿 AI 기능을 서비스 초안 기능으로 이전

### 문제

템플릿 관리 화면의 AI 새 초안 기능은 잘 동작하고 있지만, 결과가 `template`, `values.default.yaml`, `values.schema.json`, `README.md` 중심이다. 템플릿 저장소를 제거하면 이 기능을 서비스 생성의 일회성 Compose 초안 생성기로 바꿔야 한다.

### 완료 기준

- `/services/create`에서 기존 템플릿 AI와 같은 품질의 Compose 초안을 생성한다.
- 기존 template AI의 프롬프트 규칙, 모델 선택, 스트리밍, 보정 루프를 삭제하지 않고 서비스 초안용으로 이전한다.
- AI 결과는 저장 가능한 템플릿이 아니라 즉시 wizard form에 적용되는 draft다.
- AI 결과에는 rendered compose, components, generated secret keys, domain 후보, 운영 메모가 포함된다.
- AI 결과 검증은 `compose_validator`와 서비스 wizard preflight를 통과해야 성공 처리한다.

### 작업

- [x] `ai_assistant.template_contract()`의 유효한 규칙을 서비스 초안용 계약으로 이전한다.
- [x] `generate_template`, `stream_template`를 제거하고 기존 `generate_service`, `stream_service`를 서비스 초안 생성 계약으로 정리한다.
- [x] 기존 `output_format_contract("template")`의 Compose 생성 규칙, healthcheck/network/container_name 금지 규칙, Korean output 지시를 서비스 draft 계약으로 옮긴다.
- [x] `values.default.yaml`/`values.schema.json`은 저장 산출물이 아니라 제거 대상으로 결정한다.
- [ ] 첫 구현에서는 기존 template AI 출력(`template + files`)을 내부 adapter로 받아 rendered compose로 변환하고, 템플릿 저장은 하지 않는 호환 경로를 허용한다.
- [x] 최종 구현에서는 AI output을 `form`, `components`, `compose`, `notes`, `warnings` 중심으로 정리한다.
- [x] 기존 `MAX_AI_REPAIR_ATTEMPTS`, YAML/JSON 보정, line-number diagnostics, provider/model validation 로직을 유지한다.
- [x] AI 생성 결과의 README 성격 메모는 `compose_versions.metadata.draft.notes`로 매핑한다.
- [x] AI 모델 옵션 API는 서비스 생성 화면에서 계속 사용한다.
- [x] SSE event 포맷은 기존 UI와 호환되게 유지한다.

## 7. P0: 템플릿 DB 제거와 데이터 마이그레이션

### 문제

현재 core schema에 `templates`, `template_versions` 테이블이 있고, 여러 모델이 이 테이블을 조회한다. UI만 제거하면 죽은 DB 기능과 runtime 디렉터리가 남는다.

### 완료 기준

- 신규 설치 schema에서 `templates`, `template_versions` 테이블이 생성되지 않는다.
- 기존 설치 환경은 migration으로 템플릿 테이블을 제거한다.
- drop 전에 기존 서비스의 생성 원본에 필요한 템플릿 이름/namespace 정도는 legacy metadata로 보존한다.
- `template_root` 설정은 제거하거나 서비스 compose 저장 root로 이름을 바꿔 마이그레이션한다.
- cleanup/test runtime에서 `.runtime/*/templates` 의존이 사라진다.

### 작업

- [x] `src/model/db/migrations/001_core_schema.sql`에서 `templates`, `template_versions` 생성문을 제거한다.
- [x] `001_core_schema.sql`의 updated_at trigger 대상 목록에서 템플릿 테이블을 제거한다.
- [x] 신규 migration을 추가해 기존 DB에서 `template_versions`, `templates`를 drop한다.
- [x] drop 전에 `services.source_ref.template_id`가 있으면 템플릿 name/namespace를 `source_ref.legacy_template`로 복사한다.
- [x] 관련 down migration 정책을 정한다. 템플릿 기능 복구가 목적이 아니라면 rollback은 빈 테이블 재생성 수준으로 제한한다.
- [x] `011_remove_deprecated_templates.sql`는 새 제거 migration 이후 의미가 없으므로 정리 또는 no-op 처리한다.
- [x] `SETUP_TEMPLATE_ROOT_KEY`를 제거하거나 `SETUP_SERVICE_ROOT_KEY`로 대체한다.
- [x] setup 완료 payload와 status 응답에서 `template_root`를 제거한다.
- [x] 기존 `setup.template_root` 값은 서비스 파일 저장 root가 필요하면 새 key로 이관한다.
- [x] `src/model/struct/services.py`의 `template_root()` 명칭을 `service_root()` 또는 `runtime_root()`로 바꾼다.
- [x] `service_dir()`는 새 root 기준으로 유지하되 경로가 기존 서비스 파일을 잃지 않도록 migration/호환 fallback을 둔다.

## 8. P1: 백엔드 모델과 API 제거

### 문제

템플릿 모델은 seed, store, preview, release, file tree, catalog까지 여러 백엔드 경로에 흩어져 있다. DB를 제거하려면 모든 참조를 정리해야 한다.

### 완료 기준

- `wiz.model("struct").templates` 접근자가 사라진다.
- `src/model/struct/templates*.py` 파일이 제거된다.
- `page.templates` API가 제거된다.
- `infra_catalog`에서 템플릿 카운트/목록이 사라진다.
- file tree의 `scope == "template"` 분기가 사라진다.
- 서비스 생성/수정 API가 템플릿 모델을 import하지 않는다.

### 작업

- [x] `src/model/struct.py`에서 `templates` property를 제거한다.
- [x] `src/model/struct/templates.py`를 제거한다.
- [x] `src/model/struct/templates_store.py`를 제거한다.
- [x] `src/model/struct/templates_seed.py`와 seed 하위 파일을 제거한다.
- [x] `src/model/struct/templates_shared.py`를 제거한다.
- [x] `src/app/page.templates/api.py`의 AI 관련 endpoint를 서비스 생성 API로 이전한 뒤 page API를 제거한다.
- [x] `src/model/struct/infra_catalog.py`와 registry 변형에서 templates count/query를 제거한다.
- [x] `src/model/struct/file_tree.py`의 template scope를 제거한다.
- [x] `src/app/page.services.create/api.py`의 `templates_model.load`, `template_detail` endpoint를 제거한다.
- [x] `src/app/page.services/api.py`에 남아 있는 `template_detail` 또는 템플릿 선택 기반 legacy 생성 코드를 제거한다.
- [x] `src/model/struct/ai_assistant.py` 상단의 `templates_model = wiz.model("struct/templates")` 의존을 제거한다.

## 9. P1: 프론트엔드 화면 제거와 서비스 화면 통합

### 문제

`/templates` 화면은 템플릿 CRUD, release, version detail, file tree, AI create/update까지 모두 포함한다. 기능 제거 후에는 이 화면과 메뉴가 남아 있으면 제품 방향과 충돌한다.

### 완료 기준

- `/templates` route가 앱 목록에서 제거된다.
- 사이드바에 템플릿 메뉴가 보이지 않는다.
- 번역 파일의 nav templates 항목이 제거된다.
- 서비스 생성 화면 안에서 AI 초안 생성 UI가 정상 동작한다.
- 서비스 생성 화면 안에서 Compose 직접 작성 결과가 구성 확인 단계로 이어진다.

### 작업

- [x] `src/app/page.templates` 앱을 삭제한다.
- [x] `src/app/component.nav.sidebar/view.ts`에서 `/templates` 메뉴를 제거한다.
- [x] `src/assets/lang/ko.json`, `src/assets/lang/en.json`에서 nav templates 번역을 제거한다.
- [x] `/services/create`의 AI 카드가 기존 템플릿 AI modal의 모델 선택, streaming, progress compacting 로직을 재사용하게 한다.
- [x] `/services/create`에 Compose 직접 작성 editor를 추가하거나 기존 고급 Compose editor를 1단계 진입점으로 끌어올린다.
- [x] AI/직접 작성/import 결과를 공통 `applyComposeDraft` 함수로 wizard 상태에 반영한다.
- [x] `streamProgressMessage`에서 `README`, `values.schema`, `values.default`, `template metadata` 중심 표현을 서비스 draft 표현으로 정리한다.
- [x] 서비스 목록 화면의 legacy create modal 안 템플릿 선택 UI가 아직 사용 중이면 제거한다.

## 10. P1: 서비스 버전/파일/메모로 대체

### 문제

템플릿 관리의 버전 관리, 버전별 파일 보기, README 기능은 템플릿 개념과 함께 사라진다. 다만 실제 서비스에는 Compose 버전과 운영 메모가 필요하다.

### 완료 기준

- 템플릿 버전 관리는 제거한다.
- 서비스 구성 이력은 `compose_versions` 중심으로 유지한다.
- AI가 생성한 설명/README는 서비스 상세의 운영 메모나 compose version metadata에서 확인할 수 있다.
- 서비스 파일 관리는 템플릿 파일 트리가 아니라 서비스 상세 고급 기능으로만 제공한다.

### 작업

- [x] template release/version UI는 이관하지 않고 제거한다.
- [x] `compose_versions.metadata`에 AI draft summary, warnings, notes, model_ref, prompt summary 저장 여부를 결정한다.
- [x] 서비스 상세의 compose version 이력에 AI/직접 작성/import 원본을 표시한다.
- [x] AI README 결과를 저장한다면 `README.md` 파일이 아니라 `service_notes` 또는 metadata field로 저장한다.
- [x] 서비스 파일 트리는 기존 서비스 디렉터리 기준 scope로만 유지한다.
- [x] 롤백은 템플릿 버전이 아니라 compose version 기준만 유지한다.

## 11. P2: 문서와 OpenAPI 정리

### 문제

현재 문서와 OpenAPI에는 템플릿 테이블, 템플릿 파일 경로, `/api/templates`, 서비스 템플릿 기반 생성 설명이 남아 있다.

### 완료 기준

- 제품 문서에서 템플릿 관리 기능 설명이 사라진다.
- 서비스 생성 문서는 AI/직접 작성/import 기준으로 갱신된다.
- OpenAPI에서 템플릿 관리 API가 제거된다.
- runtime 문서에서 템플릿 경로가 제거된다.
- TODO 문서의 기존 템플릿 필수화 항목은 이번 방향 전환 문서로 supersede 된다.

### 작업

- [x] `docs/docker-infra-development-todo.md`의 템플릿 기반 생성 섹션을 방향 전환 내용으로 갱신한다.
- [x] `docs/docker-infra-remaining-todo.md`의 P11 템플릿 항목을 제거/대체한다.
- [x] `docs/service-management-audit-todo.md`의 템플릿 필수화 기준을 AI/Compose 초안 기준으로 갱신한다.
- [x] `docs/docker-infra-design.md`에서 `templates`, `template_versions`, `/api/templates` 설명을 제거한다.
- [x] `docs/docker-infra-runtime.md`에서 템플릿 파일 경로 설명을 제거한다.
- [x] `docs/api/openapi.json`에서 template_root, templates API, template_id 요청/응답을 제거한다.
- [x] README에 새 서비스 생성 흐름을 `AI 초안`, `Compose 직접 작성`, `Compose 가져오기`로 설명한다.

## 12. P2: 테스트 정리와 신규 검증

### 문제

현재 테스트는 `page.templates` API, 템플릿 seed, template root cleanup을 직접 검증한다. 기능 제거 후에는 삭제 테스트와 신규 서비스 생성 테스트로 대체해야 한다.

### 완료 기준

- 템플릿 API 테스트가 제거된다.
- 서비스 생성 AI draft 테스트가 추가된다.
- Compose 직접 작성 생성 테스트가 추가된다.
- 서버 Compose import 테스트는 template_id 없이 통과한다.
- DB migration 테스트에서 템플릿 테이블 제거가 확인된다.

### 작업

- [x] `tests/api/test_images_templates_catalog.py`에서 템플릿 관련 테스트를 제거하고 이미지/catalog 테스트만 남기거나 파일을 분리한다.
- [x] `tests/api/test_auth_setup.py`, `test_sample_cleanup.py`의 `page.templates` 기대값을 제거한다.
- [x] `tests/api/test_api_test_harness.py`와 cleanup helper의 `.runtime/test/templates` 의존을 제거한다.
- [x] `tests/cleanup/reset_test_environment.py`에서 template runtime root 정리를 제거하거나 새 service root로 대체한다.
- [ ] 서비스 생성 API 테스트에 `manual_compose` payload를 추가한다.
- [ ] 서비스 생성 API 테스트에 AI draft adapter 결과를 mocking해 wizard 반영을 검증한다.
- [x] migration 검증에서 `templates`, `template_versions` 테이블이 없는지 확인한다.
- [x] WIZ build를 실행해 삭제된 route/component 참조가 남지 않는지 확인한다.

## 13. P2: 하위 호환과 배포 순서

### 문제

이미 생성된 서비스는 `source_ref.template_id`를 가질 수 있고, 파일 저장 root 이름도 `template_root`를 경유한다. 단번에 삭제하면 기존 서비스 상세나 롤백에서 예상하지 못한 오류가 날 수 있다.

### 완료 기준

- 기존 서비스는 템플릿 테이블 삭제 후에도 상세, 배포, 롤백, 백업 화면이 정상 동작한다.
- 기존 서비스의 legacy source_ref는 표시하거나 무시할 수 있지만 오류를 만들지 않는다.
- 새 서비스는 더 이상 template_id를 저장하지 않는다.
- 마이그레이션은 여러 번 실행해도 안전하다.

### 작업

- [ ] migration 전에 `services.source_ref`와 `compose_versions.metadata`에서 template_id 사용 여부를 조사한다.
- [x] legacy template 정보를 보존할 최소 metadata 구조를 정의한다.
- [x] 템플릿 테이블 drop migration을 idempotent하게 작성한다.
- [x] 기존 서비스 파일 경로가 `template_root/services/{namespace}` 아래에 있으면 새 root로 옮기거나 fallback read를 제공한다.
- [ ] 배포 후 fallback read가 더 이상 필요 없을 때 제거할 cleanup TODO를 남긴다.
- [ ] 운영 환경에서 migration 전 DB backup 절차를 문서화한다.

## 14. 실행 순서

1. 서비스 생성의 새 UX/API 계약을 확정한다.
2. 템플릿 AI 기능을 서비스 draft 기능으로 복제/이전한다.
3. `/services/create`에서 AI/직접 작성/import 세 진입점을 구현한다.
4. 서비스 생성 API에서 `template_id` 요구를 제거한다.
5. 기존 템플릿 UI와 nav를 제거한다.
6. 템플릿 모델 의존을 backend에서 제거한다.
7. DB migration으로 템플릿 테이블과 setup template root를 제거/이관한다.
8. 문서, OpenAPI, 테스트를 새 방향으로 정리한다.
9. WIZ build와 API 테스트로 참조 누락을 검증한다.

이 순서는 AI 기능을 먼저 살려 둔 상태에서 UI와 DB 제거를 진행하기 위한 것이다. AI 이전이 끝나기 전에 템플릿 모델과 page API를 먼저 삭제하면 현재 잘 동작하는 프롬프트/보정 흐름을 잃을 수 있다.

## 15. 최종 검증 체크리스트

- [x] `/templates`로 접근할 수 없거나 제품 화면에서 노출되지 않는다.
- [x] 사이드바에 템플릿 메뉴가 없다.
- [ ] 새 서비스 생성에서 AI 초안으로 Compose가 생성되고 구성 확인 단계로 이어진다.
- [x] 새 서비스 생성에서 Compose 직접 작성으로 저장/배포 전 점검까지 진행된다.
- [x] 서버 Compose 가져오기가 template_id 없이 진행된다.
- [x] 신규 DB schema에 `templates`, `template_versions` 테이블이 없다.
- [ ] 기존 DB migration 후 서비스 상세/배포/롤백이 동작한다.
- [x] `rg "template_id|page.templates|struct/templates|template_versions|templates_model" project/main/src project/main/tests project/main/docs` 결과가 legacy 허용 목록만 남는다.
- [ ] AI 모델 선택, SSE streaming, 자동 보정 loop가 서비스 생성 화면에서 동작한다.
- [x] `wiz_project_build`가 통과한다.
