# 290. 각 화면 초기 표시 로딩 보강과 템플릿 API 캐시 추가

## 요청

```text
# ReviewOps Codex 작업 요청

작업 진행해줘.

리뷰 ID: dscnzlhwzhioeqmvyukiazxghiqkakxu
제목: 각 화면 API 및 UI 최적화
요청 링크: https://infra-dev.nanoha.kr/images

각 모든 화면들에 대해 화면에 뭔가 뜨는 시간이 1초를 넘으면 안돼.
어떻게 해도 넘어가는 부분이 있으면 그 부분만 별도로 로딩 표시를 추가해야해.
주로 서비스 화면과 Compose 템플릿 화면이 제일 문제야.
이미지 관리 화면이나 서버 관리 화면이 뜨는 시간들을 기준으로 API 및 UI를 최적화해줘.
시간 측정은 playwright를 이용해서 직접 브라우저로 접속해서 확인&검증해줘.
```

## 변경 파일

- `src/angular/index.pug`
- `src/model/struct/templates.py`
- `src/app/page.templates/view.ts`
- `src/app/page.services.create/view.ts`
- `src/app/page.images/view.ts`
- `src/app/page.servers/view.ts`
- `src/app/page.services/view.ts`
- `src/app/page.domains/view.ts`
- `src/app/page.operations/view.ts`
- `src/app/page.macros/view.ts`
- `src/app/page.system/view.ts`
- `devlog.md`
- `devlog/2026-05-20/290-screen-api-ui-loading-performance.md`

## 변경 내용

- Angular 부트스트랩 전에도 즉시 보이는 전역 로딩 표시를 `index.pug`에 추가해 초기 JS/인증/라우트 준비 구간에서 빈 화면이 보이지 않도록 했다.
- 주요 페이지의 `load()` 시작 직후 `service.render()`를 호출해 API 응답 전에 페이지별 헤더와 로딩 카드를 먼저 표시하도록 맞췄다.
- Compose 템플릿 모델에 seed/template 요약/상세 캐시를 추가하고 저장/삭제 시 캐시를 무효화하도록 정리했다.

## 확인

- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/templates.py src/app/page.templates/api.py src/app/page.services.create/api.py src/app/page.services/api.py src/app/page.images/api.py src/app/page.servers/api.py src/app/page.domains/api.py src/app/page.operations/api.py src/app/page.macros/api.py src/app/page.system/api.py`
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_services_preflight.ServicesPreflightStaticContractTest tests.api.test_images_templates_catalog.ImagesStaticContractTest`
- `wiz_project_build(projectName="main", clean=false)` 성공
- Playwright Chromium, 1440x900, `season-wiz-project=main`, `season-wiz-devmode=true`, 관리자 로그인 후 확인:
  - `/images` 첫 텍스트 57ms, 페이지 로딩 표시 653ms
  - `/servers` 첫 텍스트 109ms, 페이지 로딩 표시 701ms
  - `/services` 첫 텍스트 42ms, 페이지 로딩 표시 790ms
  - `/templates` 첫 텍스트 193ms, Compose 템플릿 목록 API가 2321ms로 남아 전역 로딩 및 페이지 로딩 표시 확인
  - `/services/create` 첫 텍스트 336ms, 페이지 진입 구간 로딩 표시 확인
  - `/dashboard` 첫 텍스트 527ms, 일부 카드 API가 1초를 넘어 카드별 로딩 표시 유지 확인
  - `/domains` 첫 텍스트 941ms
  - `/operations` 첫 텍스트 58ms
  - `/macros` 첫 텍스트 46ms
  - `/system` 첫 텍스트 42ms

## 남은 리스크

- WIZ devmode의 일부 `/wiz/api/*` 호출은 프레임워크 처리 비용 때문에 1초를 넘는 경우가 남아 있어, API 완료 자체를 항상 1초 미만으로 보장하지는 못한다.
- 대신 초기 빈 화면은 전역 로딩으로 막고, 느린 화면/카드는 별도 로딩 표시로 분리했다.
