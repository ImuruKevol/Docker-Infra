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
| 2026-05-08 | 065 | 백업 시스템 비활성화/초기화와 서비스 이미지 이력·백업·복원 흐름 추가 | [상세](devlog/2026-05-08/065-backup-reset-service-image-history.md) |
| 2026-05-08 | 066 | 서비스 이미지 자동 백업 정책과 수동 실행 흐름 추가 | [상세](devlog/2026-05-08/066-service-image-backup-policy.md) |
| 2026-05-08 | 067 | docker commit 기반 컨테이너 스냅샷 백업과 정책 옵션 추가 | [상세](devlog/2026-05-08/067-container-snapshot-backup.md) |
| 2026-05-08 | 068 | 백업 예약 tick/정리 정책과 서비스 생성 wizard 단계형 폼 적용 | [상세](devlog/2026-05-08/068-backup-cleanup-service-wizard.md) |
| 2026-05-08 | 069 | 서비스 생성 wizard 도메인 선택·Compose 충돌 표시·stack deploy 실행 경로 추가 | [상세](devlog/2026-05-08/069-service-wizard-domain-deploy-conflicts.md) |
| 2026-05-08 | 070 | 새 서비스 생성을 독립 화면으로 전환하고 운영자 입력 항목을 자동화 | [상세](devlog/2026-05-08/070-service-create-page-operator-flow.md) |
| 2026-05-09 | 071 | 서비스 생성 단계 단순화와 서비스 목록·상세 UX 재설계 TODO 반영 | [상세](devlog/2026-05-09/071-service-create-flow-and-service-ux-todo.md) |
| 2026-05-09 | 072 | 서비스 목록과 상세 화면을 운영자용 UX로 재구성 | [상세](devlog/2026-05-09/072-services-operator-list-detail-ux.md) |
| 2026-05-09 | 073 | 기본 서비스 템플릿을 도메인 연결 가능한 다중 서비스 스택으로 교체 | [상세](devlog/2026-05-09/073-domain-ready-service-templates.md) |
| 2026-05-09 | 074 | 서비스 생성 저장 전 자동 점검과 도메인 포트 매핑 보강 | [상세](devlog/2026-05-09/074-service-create-preflight-port-mapping.md) |
| 2026-05-09 | 075 | 서비스 배포 후 nginx server block 자동 적용과 rollback 연결 | [상세](devlog/2026-05-09/075-service-nginx-apply-rollback.md) |
| 2026-05-09 | 076 | 인증서 없는 서비스 도메인에 certbot 자동 발급 흐름 연결 | [상세](devlog/2026-05-09/076-service-certbot-auto-issue.md) |
| 2026-05-09 | 077 | 서비스 수정 wizard와 Compose 버전 갱신 흐름 추가 | [상세](devlog/2026-05-09/077-service-edit-wizard.md) |
| 2026-05-09 | 078 | Compose 버전 되돌리기와 영향 범위 확인 모달 추가 | [상세](devlog/2026-05-09/078-service-compose-rollback.md) |
| 2026-05-09 | 079 | 서비스 처리 로그 모달과 operation polling 조회 추가 | [상세](devlog/2026-05-09/079-service-operation-output-polling.md) |
| 2026-05-09 | 080 | 배포 런타임 상태 갱신, OpenSSL 자체 인증서 테스트 경로, local master 공개 서비스 배치 보강 | [상세](devlog/2026-05-09/080-service-runtime-status-self-signed-deploy-test.md) |
| 2026-05-09 | 081 | 원격 노드 배치 서비스의 서버 IP 기반 nginx upstream 적용 | [상세](devlog/2026-05-09/081-service-remote-node-nginx-upstream.md) |
| 2026-05-09 | 082 | 서버 Compose 가져오기 wizard 통합과 서비스 상세 운영 요약 보강 | [상세](devlog/2026-05-09/082-service-compose-import-wizard-runtime-ux.md) |
| 2026-05-09 | 083 | P7 nginx 고급 원문 편집과 도메인 인증서 검증·적용 서비스 표시 완료 | [상세](devlog/2026-05-09/083-p7-nginx-domain-ssl-completion.md) |
| 2026-05-09 | 084 | 서비스 관리 UX 검수 TODO와 생성/목록 자동화 보강 | [상세](devlog/2026-05-09/084-service-management-audit-automation.md) |
| 2026-05-09 | 085 | 서비스 preflight 원격 점검과 상세 고급/백업 UX 후속 보강 | [상세](devlog/2026-05-09/085-service-preflight-advanced-backup-ux.md) |
| 2026-05-09 | 086 | 서비스 삭제 기능 추가와 oo.tmpi.kr 배포 실패 원인 수정 | [상세](devlog/2026-05-09/086-service-delete-and-odoo-deploy-fix.md) |
| 2026-05-09 | 087 | oo.tmpi.kr 실제 브라우저 접속을 위한 DNS 자동 등록과 인증서 적용 보강 | [상세](devlog/2026-05-09/087-service-domain-real-browser-access.md) |
| 2026-05-09 | 088 | 서비스 상세 API helper 이름 충돌 수정과 화면 렌더링 복구 | [상세](devlog/2026-05-09/088-service-detail-helper-collision-fix.md) |
| 2026-05-09 | 089 | 서비스 배포 백그라운드 전환과 Wiki.js nginx 배포 오류 수정 | [상세](devlog/2026-05-09/089-service-background-deploy-wiki-nginx-fix.md) |
| 2026-05-09 | 090 | 서비스 상세 탭 분리와 Compose/nginx 기반 접속 흐름 표시 추가 | [상세](devlog/2026-05-09/090-service-detail-tabs-and-flow-engine.md) |
| 2026-05-09 | 091 | 서비스 접속 흐름을 캔버스형 시스템 구성도로 전환 | [상세](devlog/2026-05-09/091-service-flow-canvas-diagram.md) |
| 2026-05-09 | 092 | 서비스 플로우 구성도 좌표계 통합과 화살표 정렬 수정 | [상세](devlog/2026-05-09/092-service-flow-svg-coordinate-fix.md) |
| 2026-05-09 | 093 | 서비스 플로우를 nginx 방화벽 중심 트리 구조로 재구성 | [상세](devlog/2026-05-09/093-service-flow-tree-firewall-layout.md) |
| 2026-05-09 | 094 | 서버 관리 개요 UX와 컨테이너 삭제, 운영형 access 화면 적용 | [상세](devlog/2026-05-09/094-server-overview-access-operator-ux.md) |
| 2026-05-09 | 095 | 미등록 컨테이너 목록 제거와 서비스 고급 관리 Monaco/컨테이너 액션 적용 | [상세](devlog/2026-05-09/095-service-advanced-monaco-container-actions.md) |
| 2026-05-09 | 096 | 서버 리소스 모니터링 CSV 기록과 자동 배치 점수화 적용 | [상세](devlog/2026-05-09/096-node-resource-history-auto-placement.md) |
| 2026-05-09 | 097 | 서버 모니터링 백그라운드 수집과 컨테이너 ID 액션·공통 파일 트리 적용 | [상세](devlog/2026-05-09/097-monitoring-container-id-file-tree.md) |
| 2026-05-09 | 098 | 파일 트리 홈 기본 경로·보호 경로와 모니터링/컨테이너/이미지 액션 보강 | [상세](devlog/2026-05-09/098-file-tree-monitoring-actions-hardening.md) |
| 2026-05-10 | 099 | digest 포함 로컬 이미지 삭제 보강과 odoo 이미지 실제 삭제 | [상세](devlog/2026-05-10/099-local-image-digest-delete-odoo-removal.md) |
| 2026-05-10 | 100 | 서비스 삭제 시 stack 볼륨 제거와 서버 자원 추이 차트/기록 삭제 UI 추가 | [상세](devlog/2026-05-10/100-service-delete-volumes-resource-chart.md) |
| 2026-05-10 | 101 | 자원 차트 Chart.js 전환과 기간 조회·파일 트리 성능 최적화 | [상세](devlog/2026-05-10/101-chartjs-date-range-file-tree-performance.md) |
| 2026-05-10 | 102 | Chart.js canvas 참조와 렌더 타이밍 수정 | [상세](devlog/2026-05-10/102-chartjs-canvas-reference-render-timing.md) |
| 2026-05-10 | 103 | Chart.js template reference NG0301 제거 | [상세](devlog/2026-05-10/103-chartjs-ng0301-reference-removal.md) |
