| 날짜 | ID | 작업 내용 | 상세 |
|------|-----|----------|------|
| 2026-05-06 | 001 | Docker Infra 핵심 설계 문서 추가 | [상세](devlog/2026-05-06/001-docker-infra-design-doc.md) |
| 2026-05-06 | 002 | Docker Infra 마스터 노드와 Swarm 로드밸런싱 설계 반영 | [상세](devlog/2026-05-06/002-master-node-swarm-load-balancing.md) |
| 2026-05-06 | 003 | Docker Infra 실제 개발 TODO 문서 추가 | [상세](devlog/2026-05-06/003-docker-infra-development-todo.md) |
| 2026-05-06 | 004 | 샘플 소스 및 devlog 정리 후 Docker Infra 앱 골격 구성 | [상세](devlog/2026-05-06/004-sample-cleanup-docker-infra-shell.md) |
| 2026-05-06 | 005 | Docker Infra conda 실행 환경 명시 | [상세](devlog/2026-05-06/005-conda-runtime-environment.md) |
| 2026-05-06 | 006 | 시스템 health API 계약과 라우트 추가 | [상세](devlog/2026-05-06/006-system-health-api-contract.md) |
| 2026-05-06 | 007 | 개발/테스트 compose와 runtime 격리 정책 추가 | [상세](devlog/2026-05-06/007-dev-test-compose-runtime-isolation.md) |
| 2026-05-06 | 008 | OpenAPI/Swagger 공통 계약과 schema 검증 테스트 보강 | [상세](devlog/2026-05-06/008-openapi-swagger-common-contracts.md) |
| 2026-05-06 | 009 | API 테스트 공통 클라이언트와 cleanup 하네스 추가 | [상세](devlog/2026-05-06/009-api-test-client-cleanup-harness.md) |
| 2026-05-06 | 010 | Playwright E2E 테스트 기반 추가 | [상세](devlog/2026-05-06/010-playwright-e2e-foundation.md) |
| 2026-05-06 | 011 | PostgreSQL migration 체계와 핵심 테이블 구현 | [상세](devlog/2026-05-06/011-postgresql-migrations-core-tables.md) |
| 2026-05-06 | 012 | Password-only 인증과 설치 마법사 구현 | [상세](devlog/2026-05-06/012-password-auth-setup-wizard.md) |
| 2026-05-06 | 013 | 시스템 설정 화면과 동적 메뉴 구현 | [상세](devlog/2026-05-06/013-system-settings-dynamic-menu.md) |
| 2026-05-06 | 014 | Job/Step/Log 모델과 API 구현 | [상세](devlog/2026-05-06/014-job-step-log-api.md) |
| 2026-05-06 | 015 | Secret masking과 로그 검색/다운로드 구현 | [상세](devlog/2026-05-06/015-secret-masking-log-retention.md) |
| 2026-05-06 | 016 | Local Executor와 local command check API 구현 | [상세](devlog/2026-05-06/016-local-executor-command-check.md) |
| 2026-05-06 | 017 | Local Master ensure와 Slave join 구현 | [상세](devlog/2026-05-06/017-local-master-slave-join.md) |
| 2026-05-07 | 018 | Node Reporter와 서버 상세 API/UI 구현 | [상세](devlog/2026-05-07/018-node-reporter-server-detail.md) |
| 2026-05-07 | 019 | Compose 검증기와 validation API 구현 | [상세](devlog/2026-05-07/019-compose-validator-api.md) |
| 2026-05-07 | 020 | Docker Infra WIZ model/struct 구조 리팩토링 | [상세](devlog/2026-05-07/020-wiz-model-struct-refactor.md) |
| 2026-05-07 | 021 | WIZ controller/API 응답 패턴과 Struct 경계 리팩토링 | [상세](devlog/2026-05-07/021-wiz-controller-api-response-structure.md) |
| 2026-05-07 | 022 | Docker Infra 런타임 DB/env 설정을 WIZ config와 데몬 주입으로 정리 | [상세](devlog/2026-05-07/022-runtime-config-env-daemon.md) |
| 2026-05-07 | 023 | Docker Infra 운영 콘솔 화면 구현 | [상세](devlog/2026-05-07/023-docker-infra-ui-console.md) |
| 2026-05-07 | 024 | 관리자용 UX TODO 반영과 서버/서비스 화면 흐름 개선 | [상세](devlog/2026-05-07/024-admin-ux-service-flow.md) |
| 2026-05-07 | 025 | 서버 관리 모달 UX와 관리용 SSH key 등록 흐름 보강 | [상세](devlog/2026-05-07/025-server-modal-ssh-key-flow.md) |
| 2026-05-07 | 026 | 서버 수정 모달, master 고정 목록, 자동 갱신과 SSH 오류 안내 보강 | [상세](devlog/2026-05-07/026-server-edit-auto-refresh.md) |
| 2026-05-07 | 027 | 서버 상세 metric 경량 갱신과 서비스/컨테이너 제어 흐름 보강 | [상세](devlog/2026-05-07/027-server-runtime-service-grouping.md) |
| 2026-05-07 | 028 | 서비스 화면 모달 UX와 SSH 비밀번호 프롬프트 처리 보강 | [상세](devlog/2026-05-07/028-services-modal-ssh-password-fix.md) |
| 2026-05-07 | 029 | 서버 상세 cached 초기 렌더와 미등록 Compose 등록 UX 최적화 | [상세](devlog/2026-05-07/029-server-cached-detail-compose-import.md) |
| 2026-05-07 | 030 | 서버 목록 load API 경량화와 background 상세 분리 | [상세](devlog/2026-05-07/030-servers-load-api-fast-path.md) |
| 2026-05-07 | 031 | Compose 파일 선택 모달 기본 홈 경로와 직접 경로 이동 추가 | [상세](devlog/2026-05-07/031-compose-browser-home-path.md) |
| 2026-05-07 | 032 | 인증·설정 중복 호출 제거와 컨테이너 액션/Compose 오류 안내 보강 | [상세](devlog/2026-05-07/032-auth-settings-container-action-compose-errors.md) |
| 2026-05-07 | 033 | 서버 상세 metric 응답 경량화와 Compose 경고/SSH 등록 흐름 보강 | [상세](devlog/2026-05-07/033-servers-metric-compose-ssh-flow.md) |
| 2026-05-07 | 034 | Compose 파일 등록 모달에 서비스 이름 입력 추가 | [상세](devlog/2026-05-07/034-compose-import-service-name.md) |
| 2026-05-07 | 035 | 서버 상세 race 방지, Docker 미설치 안내, SSH key 표시 정리와 서버 매크로 실행 기능 추가 | [상세](devlog/2026-05-07/035-servers-race-docker-macro-ui.md) |
| 2026-05-07 | 036 | 전역 매크로 관리 화면, 서버 상세 탭형 매크로/웹 터미널, Monaco 다크모드·저장 단축키 적용 | [상세](devlog/2026-05-07/036-global-macros-terminal-tabs.md) |
| 2026-05-07 | 037 | 공통 검색형 매크로 선택 컴포넌트와 서버 상세 매크로/웹 터미널 UX 보강 | [상세](devlog/2026-05-07/037-macro-select-terminal-ux.md) |
| 2026-05-07 | 038 | 서버 상세 매크로 선택 뱃지 정렬과 실행 인자 기본 비활성 UX 적용 | [상세](devlog/2026-05-07/038-macro-badge-args-default-off.md) |
| 2026-05-07 | 039 | 서버 상세 CPU/Memory/Storage 프로그레스바와 부드러운 갱신 애니메이션 추가 | [상세](devlog/2026-05-07/039-server-metric-progress-bars.md) |
| 2026-05-07 | 040 | 전역 매크로 목록 버튼 위치 조정과 서버 상세 매크로 실행 로그 스트리밍 적용 | [상세](devlog/2026-05-07/040-macros-button-streaming.md) |
| 2026-05-07 | 041 | 서버 상세 웹 터미널 집중 보기 토글과 전체 폭 확장 레이아웃 적용 | [상세](devlog/2026-05-07/041-web-terminal-expand-toggle.md) |
| 2026-05-07 | 042 | devlog 내 테스트 비밀번호 등 민감값을 placeholder로 정리 | [상세](devlog/2026-05-07/042-devlog-sensitive-redaction.md) |
| 2026-05-07 | 043 | 운영 콘솔 앱 셸 브랜딩/사이드바 정리와 누락 devlog 보강 | [상세](devlog/2026-05-07/043-app-shell-sidebar-catchup.md) |
| 2026-05-07 | 044 | 시스템 설정 실적용, Harbor/GitLab 연결 테스트, Cloudflare 도메인 관리 화면과 DNS 캐시 구조 추가 | [상세](devlog/2026-05-07/044-system-settings-domains-cloudflare.md) |
| 2026-05-07 | 045 | appearance 로딩을 auth 체크에서 분리하고 Angular 초기 1회 로드로 최적화 | [상세](devlog/2026-05-07/045-appearance-app-initializer.md) |
| 2026-05-07 | 046 | 시스템 설정 화면의 파일 업로드 template ref 오류를 제거해 Angular 런타임 예외 수정 | [상세](devlog/2026-05-07/046-system-page-upload-ref-fix.md) |
| 2026-05-07 | 047 | 시스템 설정 웹서버/브랜딩 정리, 도메인 관리 필터/SSL 개선, 공통 모달 취소 라벨 정비 | [상세](devlog/2026-05-07/047-system-domains-webserver-modal-cleanup.md) |
| 2026-05-07 | 048 | 시스템 설정 SVG/지연 업로드, 로컬 경로 선택 모달, 도메인 A 레코드 공통 검색 선택 적용 | [상세](devlog/2026-05-07/048-system-assets-path-picker-domain-search-select.md) |
| 2026-05-07 | 049 | 브랜딩 자산 고정 라우트와 시스템 설정 URL 입력 제거 적용 | [상세](devlog/2026-05-07/049-fixed-branding-asset-routes.md) |
| 2026-05-07 | 050 | 시스템 설정 인증서 UUID fallback, 파일 경로 선택 parent fallback, 파일 트리 모달 스크롤 제한 적용 | [상세](devlog/2026-05-07/050-system-path-picker-and-certificate-modal-fixes.md) |
| 2026-05-07 | 051 | 이미지/템플릿 관리 화면 완성과 기본 템플릿 seed, 서비스 생성 템플릿 연동 적용 | [상세](devlog/2026-05-07/051-images-templates-catalog-and-service-template-flow.md) |
| 2026-05-08 | 052 | 이미지/템플릿 화면 Angular templateUrl 해석 오류 수정 | [상세](devlog/2026-05-08/052-images-templates-component-resolution-fix.md) |
| 2026-05-08 | 053 | 이미지 관리 초기 로딩 분리·Harbor 삭제/태그 표시 보강, 템플릿 릴리즈 UI·저장 경로·기본 seed 확장 | [상세](devlog/2026-05-08/053-images-performance-template-release-ui.md) |
| 2026-05-08 | 054 | 이미지 관리 로컬 일괄 삭제, Harbor 프로젝트 생성, 저장소별 태그 상세/삭제 흐름 보강 | [상세](devlog/2026-05-08/054-images-local-bulk-delete-harbor-project-create.md) |
| 2026-05-08 | 055 | Harbor 이미지 목록/태그 목록 분리와 저장소 선택·삭제 동작 수정 | [상세](devlog/2026-05-08/055-harbor-repository-list-tag-loading-fix.md) |
| 2026-05-08 | 056 | Harbor 이미지 목록과 태그 목록을 좌우 2단 패널로 재배치 | [상세](devlog/2026-05-08/056-harbor-tags-right-panel-layout.md) |
| 2026-05-08 | 057 | GitLab 연동과 build→Harbor push 흐름 제거, 이미지 전용 운영 구조로 정리 | [상세](devlog/2026-05-08/057-remove-gitlab-build-flow.md) |
| 2026-05-08 | 058 | nginx 고정 운영 기준 적용, 시스템 SSL 설정 제거, 도메인 인증서 업로드와 서비스 생성 흐름 단순화 | [상세](devlog/2026-05-08/058-fixed-nginx-domain-certs-service-flow.md) |
| 2026-05-08 | 059 | Job 제거·내장 Harbor 백업 시스템·관리자용 서비스 wizard 기준으로 TODO 전면 재작성 | [상세](devlog/2026-05-08/059-rewrite-todo-for-simplified-product-flow.md) |
| 2026-05-08 | 060 | 서비스-도메인 nginx 연결 wizard TODO 반영과 P0 문서/OpenAPI 정리 | [상세](devlog/2026-05-08/060-service-domain-nginx-wizard-p0-docs-openapi.md) |
| 2026-05-08 | 061 | Job route/model 제거와 operation log 기반 실행 기록 전환 | [상세](devlog/2026-05-08/061-remove-job-system-operation-log.md) |
| 2026-05-08 | 062 | 최초 구성 마법사 백업 시스템 토글과 설정 스키마 추가 | [상세](devlog/2026-05-08/062-setup-backup-system-toggle-schema.md) |
| 2026-05-08 | 063 | WIZ 구조 계약에 맞춘 대형 모델 분리와 api.py 응답 위치 정리 | [상세](devlog/2026-05-08/063-wiz-structure-model-split-cleanup.md) |
| 2026-05-08 | 064 | 외부 Harbor 설정 제거와 내장 로컬 Harbor 백업 시스템 실행 경로 연결 | [상세](devlog/2026-05-08/064-local-harbor-backup-runtime.md) |
