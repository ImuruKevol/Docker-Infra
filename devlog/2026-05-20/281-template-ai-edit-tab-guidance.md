# 281. 템플릿 편집 AI 버튼과 탭별 표준 안내 UX 개선

## 요청

> 작업 진행해줘.
>
> 템플릿 편집 시에도 AI 템플릿 초안 카드가 보이고 있어. 템플릿 편집 시에는 이 카드가 보이지 않아야 하고, 그냥 탭들 오른쪽에 AI 수정/점검 버튼을 추가해서 서비스 상세에서 AI 수정/점검 버튼처럼 동작시키면 돼.
> 그리고 AI 템플릿 초안 카드의 UI도 싹 갈아엎어야 해. 일단 AI 허용 범위는 안보여줘도 되니까 삭제하고, 템플릿 표준만 AI 템플릿 초안 카드에 있는게 아니라 별도로 분리해서 Compose, 기본값, Schema 탭의 오른쪽이나 왼쪽에 조금 더 상세하게 각 탭에 맞는 설명으로 보완해서 보여줘야해.
> 그리고 요청 내용과 사용할 모델이 한 행에 있는데, 이건 UX를 아예 개무시한 레이아웃이야.

## 변경 파일

- `src/app/page.templates/view.pug`
- `src/app/page.templates/view.ts`
- `tests/api/test_services_preflight.py`
- `devlog.md`
- `devlog/2026-05-20/281-template-ai-edit-tab-guidance.md`

## 변경 내용

- 기존 템플릿 편집 상태에서는 AI 템플릿 초안 카드가 보이지 않도록 `!isEditingTemplate()` 조건을 추가했다.
- 편집 탭 우측에 `AI 수정/점검` 버튼을 추가하고, 서비스 상세 AI 검사/수정처럼 모달에서 요청과 모델을 입력한 뒤 기존 템플릿 AI 스트림을 재사용해 현재 화면에 수정안을 반영하도록 구성했다.
- AI 템플릿 초안 카드를 신규 템플릿 작성 전용으로 재배치하고, 요청 내용과 모델 선택을 분리해 세로 흐름으로 정리했다.
- 화면에서 `AI 허용 범위` 노출을 제거했다.
- Compose, 기본값, Schema 탭에 각각 맞는 표준 안내를 AI 카드 밖의 별도 안내 영역으로 분리했다.
- 템플릿 AI 수정 시 기존 템플릿 namespace가 AI 응답 때문에 새 템플릿으로 바뀌지 않도록 현재 편집 대상 namespace를 유지했다.
- 정적 계약 테스트를 새 UX 문구와 표시 조건 기준으로 갱신했다.

## 확인

- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/app/page.templates/api.py src/model/struct/templates.py src/model/struct/templates_seed.py src/model/struct/ai_assistant.py`
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_services_preflight.ServicesPreflightStaticContractTest`
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_services_preflight.ServicesPreflightStaticContractTest tests.api.test_images_templates_catalog.ImagesStaticContractTest tests.api.test_migration_schema.MigrationSchemaStaticContractTest`
- `wiz_project_build(projectName="main", clean=false)`
- `curl`로 `http://127.0.0.1:3001/api/system/health` 200 확인
- `season-wiz-project=main`, `season-wiz-devmode=true` 쿠키를 넣고 Playwright로 로컬/실도메인 `/templates` 접근을 시도했으나 둘 다 `/access`로 리다이렉트됨. console/page error는 없었고, 인증 비밀번호 환경변수는 설정되어 있지 않아 인증 후 화면 검증은 수행하지 못했다.

## 남은 리스크

- 인증 후 실제 템플릿 편집 화면에서 AI 버튼 표시, 카드 숨김, 탭별 안내 노출을 브라우저로 직접 확인하지 못했다.
- 실제 AI 수정 호출은 비용과 시간이 큰 작업이라 이번 검증에서는 수행하지 않았다.
