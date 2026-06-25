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
| 2026-05-10 | 104 | 파일 트리 렌더 누락과 서버 자원 자동 갱신 지연 개선 | [상세](devlog/2026-05-10/104-file-tree-render-auto-refresh-cpu.md) |
| 2026-05-10 | 105 | 모니터링 자동 구성과 10분 주기 백그라운드 수집 분리 | [상세](devlog/2026-05-10/105-monitoring-auto-config-daemon-interval.md) |
| 2026-05-10 | 106 | 웹 요청 기반 모니터링 데몬 시작 제거와 systemd 상태 확인 정리 | [상세](devlog/2026-05-10/106-monitoring-systemd-only-no-web-trigger.md) |
| 2026-05-10 | 107 | 도메인 관리 레코드 UI와 DNS 기본값 정리 | [상세](devlog/2026-05-10/107-domain-management-record-ui-search-select.md) |
| 2026-05-10 | 108 | 도메인 인증서 서비스 상세 링크와 Search Select 선택 타이밍 보강 | [상세](devlog/2026-05-10/108-domain-service-link-search-select-mousedown.md) |
| 2026-05-10 | 109 | 시스템 설정 탭 구조와 AI 설정/모델 조회/자원 확인 추가 | [상세](devlog/2026-05-10/109-system-ai-settings.md) |
| 2026-05-10 | 110 | AI 모델 상세 메타데이터와 Search Select 적용 | [상세](devlog/2026-05-10/110-ai-model-metadata-search-select.md) |
| 2026-05-10 | 111 | 템플릿/서비스 AI 생성 계약과 자동 구성 UI 연결 | [상세](devlog/2026-05-10/111-ai-template-service-assistant.md) |
| 2026-05-10 | 112 | AI 사용 화면 모델 선택과 Thinking 스트림 UI 추가 | [상세](devlog/2026-05-10/112-ai-model-picker-thinking-stream.md) |
| 2026-05-10 | 113 | 템플릿 상세 버전 탭 분리와 AI 수정안 적용/롤백 추가 | [상세](devlog/2026-05-10/113-template-version-tabs-ai-edit-proposal.md) |
| 2026-05-10 | 114 | AI 사용 모델 선택 범위와 진행 스트림 표시 정리 | [상세](devlog/2026-05-10/114-ai-selected-models-stream-validation.md) |
| 2026-05-10 | 115 | AI 진행 상태 갱신 표시와 한국어 결과 생성 지시 보강 | [상세](devlog/2026-05-10/115-ai-progress-line-korean-output.md) |
| 2026-05-10 | 116 | AI 템플릿 values YAML 보정과 placeholder 기본값 보강 | [상세](devlog/2026-05-10/116-ai-template-values-yaml-repair.md) |
| 2026-05-10 | 117 | AI 템플릿 Compose placeholder YAML-safe 보정 | [상세](devlog/2026-05-10/117-ai-template-compose-placeholder-repair.md) |
| 2026-05-10 | 118 | AI output 검증 실패 시 모델 재요청 보정 루프 적용 | [상세](devlog/2026-05-10/118-ai-output-repair-retry.md) |
| 2026-05-10 | 119 | AI 템플릿 수정안 YAML 보정 재요청 진단 강화 | [상세](devlog/2026-05-10/119-ai-template-yaml-repair-diagnostics.md) |
| 2026-05-10 | 120 | AI output 포맷 계약과 values 기본값 객체 반환 규칙 추가 | [상세](devlog/2026-05-10/120-ai-output-format-contract.md) |
| 2026-05-10 | 121 | AI 재시도 20회 확대와 Gemini 템플릿 수정 실검증 | [상세](devlog/2026-05-10/121-ai-retry-20-gemini-template-verification.md) |
| 2026-05-11 | 122 | AI 설정 카드별 저장과 등록 노드 Ollama 스캔 UI 추가 | [상세](devlog/2026-05-11/122-ai-settings-card-save-node-ollama-scan.md) |
| 2026-05-11 | 123 | 템플릿 기능 제거와 AI 서비스 초안 이전 TODO 문서 추가 | [상세](devlog/2026-05-11/123-template-removal-todo.md) |
| 2026-05-11 | 124 | 서비스 생성 화면 AI 우선 UX와 자동 보정 컨텍스트 보강 | [상세](devlog/2026-05-11/124-service-create-ai-first-ux.md) |
| 2026-05-11 | 125 | 대시보드 서버 자원 추이 기간 필터와 DB fallback 보강 | [상세](devlog/2026-05-11/125-dashboard-resource-range-db-fallback.md) |
| 2026-05-11 | 126 | 노드 자원 수집 systemd timer 자동 구성 | [상세](devlog/2026-05-11/126-node-metrics-systemd-collector.md) |
| 2026-05-11 | 127 | 서비스 생성 AI 초안 후 2단계 진행 차단 수정 | [상세](devlog/2026-05-11/127-service-create-step2-validation-fix.md) |
| 2026-05-11 | 128 | 대시보드 서버별 자원 차트와 1분 중복 샘플 방어 | [상세](devlog/2026-05-11/128-dashboard-node-resource-charts-dedupe.md) |
| 2026-05-11 | 129 | 자원 수집 web 의존 제거와 collector timer 복구 | [상세](devlog/2026-05-11/129-monitoring-web-independent-collector-repair.md) |
| 2026-05-11 | 130 | AI 서비스 초안 이미지 이름과 버전 검증 보강 | [상세](devlog/2026-05-11/130-ai-service-draft-image-version-validation.md) |
| 2026-05-11 | 131 | 로컬 AI 서비스 생성 스트림 장시간 대기 보강 | [상세](devlog/2026-05-11/131-local-ai-service-stream-timeout.md) |
| 2026-05-11 | 132 | AI SSE chunked 응답 중단 방어 | [상세](devlog/2026-05-11/132-ai-sse-incomplete-chunked-guard.md) |
| 2026-05-12 | 133 | AI 서비스 생성 스트림 heartbeat 전달 누락 수정 | [상세](devlog/2026-05-12/133-ai-service-stream-heartbeat-forwarding.md) |
| 2026-05-12 | 134 | AI 이미지 태그 자동 보정과 서비스 생성 preflight 중복 호출 방지 | [상세](devlog/2026-05-12/134-ai-image-resolution-preflight-cache.md) |
| 2026-05-12 | 135 | 서비스 수정 모달 섹션형 레이아웃으로 재구성 | [상세](devlog/2026-05-12/135-service-edit-modal-section-layout.md) |
| 2026-05-12 | 136 | Codex 기반 AI 실행 게이트웨이와 Docker Infra MCP 추가 | [상세](devlog/2026-05-12/136-codex-ai-gateway-mcp.md) |
| 2026-05-12 | 137 | 서비스 생성/수정 AI를 수정된 Codex CLI 직접 실행 플로우로 전환 | [상세](devlog/2026-05-12/137-codex-cli-direct-ai-runtime.md) |
| 2026-05-12 | 138 | Codex CLI debug 빌드와 로컬 Responses smoke 테스트로 실행 리스크 보완 | [상세](devlog/2026-05-12/138-codex-cli-build-smoke.md) |
| 2026-05-12 | 139 | 서비스 삭제 시 Cloudflare DNS 레코드 정리 추가 | [상세](devlog/2026-05-12/139-service-delete-cloudflare-dns-cleanup.md) |
| 2026-05-12 | 140 | AI 서비스 생성/수정 2단계 보정 플로우와 Docker Infra MCP 상태 조회 도구 보강 | [상세](devlog/2026-05-12/140-ai-multiphase-codex-mcp-inspection.md) |
| 2026-05-12 | 141 | 다중 도메인 AI 생성과 배포 후 AI 런타임 복구 플로우 추가 | [상세](devlog/2026-05-12/141-ai-runtime-repair-multidomain.md) |
| 2026-05-12 | 142 | Codex CLI 실행 파일 탐색과 자동 빌드 fallback 보강 | [상세](devlog/2026-05-12/142-codex-cli-executable-resolution.md) |
| 2026-05-12 | 143 | Codex CLI 소스 변경 감지 기반 cargo 자동 빌드 보강 | [상세](devlog/2026-05-12/143-codex-cli-stale-source-auto-build.md) |
| 2026-05-12 | 144 | 서비스 AI 런타임 검사/수정 진단 조건 불일치 수정 | [상세](devlog/2026-05-12/144-service-ai-runtime-repair-diagnostics-fix.md) |
| 2026-05-12 | 145 | 서비스 AI 검사에 화면 표시 실패 로그 신호 병합 | [상세](devlog/2026-05-12/145-service-ai-visible-failed-operation-signal.md) |
| 2026-05-12 | 146 | AI 런타임 검사 사용자 프롬프트와 컨테이너 터미널 조치 도구 추가 | [상세](devlog/2026-05-12/146-service-ai-runtime-terminal-actions.md) |
| 2026-05-12 | 147 | 서비스 AI 수정 코멘트와 런타임 스트리밍 적용/컨테이너 조치 실행 보강 | [상세](devlog/2026-05-12/147-service-ai-runtime-stream-apply-actions.md) |
| 2026-05-12 | 148 | AI 런타임 검사 스트림 완료 검증과 강제 AI 분석 실행 보강 | [상세](devlog/2026-05-12/148-service-ai-runtime-stream-completion-guard.md) |
| 2026-05-12 | 149 | 매크로 첨부 파일 저장과 실행 전 서버 전송 기능 추가 | [상세](devlog/2026-05-12/149-macro-file-attachments.md) |
| 2026-05-12 | 150 | 매크로 첨부 파일 DB 스키마 수동 적용 | [상세](devlog/2026-05-12/150-macro-file-schema-apply.md) |
| 2026-05-12 | 151 | 매크로 스크립트 CRLF 줄바꿈 정규화 | [상세](devlog/2026-05-12/151-macro-script-crlf-normalization.md) |
| 2026-05-12 | 152 | 서비스 AI Codex Agent 입력·권한·MCP scope 설계와 allowlist 적용 | [상세](devlog/2026-05-12/152-service-ai-codex-agent-scope-design.md) |
| 2026-05-12 | 153 | 서비스 AI 보완 검토와 배포 검증 MCP·중복 배포 방지 보강 | [상세](devlog/2026-05-12/153-service-ai-verification-mcp-duplicate-guard.md) |
| 2026-05-12 | 154 | AI 백그라운드 검증 조회와 일반 사용자용 MCP 권한 확장 | [상세](devlog/2026-05-12/154-service-ai-background-verification-permissions.md) |
| 2026-05-13 | 155 | 서비스 생성 배포 시 AI 검증 자동 시작 제거 | [상세](devlog/2026-05-13/155-service-ai-verification-explicit-start.md) |
| 2026-05-13 | 156 | AI 검증 로그 압축과 실패 후 재시도 플로우 보강 | [상세](devlog/2026-05-13/156-service-ai-verification-retry-log-flow.md) |
| 2026-05-13 | 157 | bbb Jitsi 서비스 직접 복구와 AI 런타임 compose 계약 보강 | [상세](devlog/2026-05-13/157-bbb-service-ai-runtime-contract.md) |
| 2026-05-13 | 158 | Codex 로그인 실행 설정과 AI 점검 모델 선택 추가 | [상세](devlog/2026-05-13/158-codex-login-settings-ai-model-picker.md) |
| 2026-05-13 | 159 | AI 모델 목록 Codex 상단 항목과 커스텀 CLI 경유 표시 정리 | [상세](devlog/2026-05-13/159-codex-top-model-custom-cli-routing.md) |
| 2026-05-13 | 160 | AI 모델 선택 기본값 Codex 우선 고정 | [상세](devlog/2026-05-13/160-codex-default-model-ref.md) |
| 2026-05-13 | 161 | AI 실행 스트림의 Codex CLI 경로 확인 표시 보강 | [상세](devlog/2026-05-13/161-ai-codex-cli-execution-visibility.md) |
| 2026-05-13 | 162 | 시스템 설정 AI 탭 서브탭화와 모델 표시 순서 옵션 추가 | [상세](devlog/2026-05-13/162-system-ai-subtabs-model-order.md) |
| 2026-05-13 | 163 | Codex 로그인 상태 판정과 커스텀 CLI 표시 제거 | [상세](devlog/2026-05-13/163-codex-login-status-custom-cli-hide.md) |
| 2026-05-13 | 164 | 서버 자원 10분 통계 집계와 min/max area 차트 적용 | [상세](devlog/2026-05-13/164-node-resource-window-area-chart.md) |
| 2026-05-13 | 165 | 노드 로컬 1초 샘플링 10분 집계와 ApexCharts 분리 차트 적용 | [상세](devlog/2026-05-13/165-node-local-rollup-apexcharts.md) |
| 2026-05-13 | 166 | 모달 레이어와 서버별 자원 차트 탭 UI 수정 | [상세](devlog/2026-05-13/166-modal-layout-node-chart-tabs.md) |
| 2026-05-13 | 167 | 자원 차트 시간대 정규화와 ApexCharts hover 시간 표시 보강 | [상세](devlog/2026-05-13/167-resource-chart-timezone-tooltip.md) |
| 2026-05-13 | 168 | CPU/Memory min-max 차트와 Storage 단일 측정 수집 로직 정리 | [상세](devlog/2026-05-13/168-resource-minmax-storage-single-sample.md) |
| 2026-05-13 | 169 | 대시보드 카드 정리와 작업 로그 조회 화면 추가 | [상세](devlog/2026-05-13/169-dashboard-operations-log.md) |
| 2026-05-13 | 170 | 대시보드 배치·도메인 조회·ApexCharts hover와 자원 min/max 보정 | [상세](devlog/2026-05-13/170-dashboard-domain-chart-fixes.md) |
| 2026-05-13 | 171 | 대시보드 등록 도메인 목록 표시 기준 단순화 | [상세](devlog/2026-05-13/171-dashboard-registered-domain-list.md) |
| 2026-05-13 | 172 | 대시보드 도메인 카드 조회 SQL 확정과 서비스 재시작 반영 | [상세](devlog/2026-05-13/172-dashboard-domain-card-runtime-fix.md) |
| 2026-05-13 | 173 | CPU/Memory 자원 차트 hover tooltip min-max 표시 보강 | [상세](devlog/2026-05-13/173-resource-tooltip-minmax.md) |
| 2026-05-13 | 174 | 작업 로그 페이지네이션과 개수 select 폭 보정 | [상세](devlog/2026-05-13/174-operations-pagination-select-width.md) |
| 2026-05-13 | 175 | 작업 로그 전체 건수 fallback과 페이지 버튼 보강 | [상세](devlog/2026-05-13/175-operations-pagination-total-fallback.md) |
| 2026-05-13 | 176 | 서버 자원 수집 자동 점검 작업 로그 제거 | [상세](devlog/2026-05-13/176-node-monitoring-repair-log-suppression.md) |
| 2026-05-13 | 177 | 서버 상세 등록 서비스 매칭 복구 | [상세](devlog/2026-05-13/177-server-detail-service-matching.md) |
| 2026-05-13 | 178 | 서버 상세 카드 제거와 전역 매크로 실행 전용화 | [상세](devlog/2026-05-13/178-server-detail-global-macros.md) |
| 2026-05-13 | 179 | 서버 상세 매크로 전역 표시 제거 | [상세](devlog/2026-05-13/179-server-macro-global-label-cleanup.md) |
| 2026-05-13 | 180 | 서버 상세 매크로 실행 인자 체크박스 폭 축소 | [상세](devlog/2026-05-13/180-server-macro-args-checkbox-width.md) |
| 2026-05-13 | 181 | 사이드 메뉴 카테고리 분리와 도구 다운로드 제거 | [상세](devlog/2026-05-13/181-sidebar-menu-groups-remove-tools.md) |
| 2026-05-13 | 182 | 대시보드 카드 단위 API 분리와 부분 로딩 적용 | [상세](devlog/2026-05-13/182-dashboard-card-api-split.md) |
| 2026-05-13 | 183 | 서비스 상세 탭 API 분리와 지연 로딩 적용 | [상세](devlog/2026-05-13/183-service-detail-tab-api-split.md) |
| 2026-05-13 | 184 | 서비스 상세 구성 탭 실행 상태와 원문/파일/버전 탭 재구성 | [상세](devlog/2026-05-13/184-service-detail-runtime-tabs.md) |
| 2026-05-14 | 185 | 서비스 상세 구성 탭 관리자 친화 UI 정리 | [상세](devlog/2026-05-14/185-service-detail-admin-friendly-ui.md) |
| 2026-05-14 | 186 | 서비스 상세 탭 카드와 헤더 디자인 통일 | [상세](devlog/2026-05-14/186-service-detail-tab-design-unification.md) |
| 2026-05-14 | 187 | 서비스 관리 API 상세/목록 경량화와 지연 로딩 최적화 | [상세](devlog/2026-05-14/187-service-management-api-optimization.md) |
| 2026-05-14 | 188 | 이미지 관리 Harbor 토글 숨김, 로컬 용량 표시와 삭제 예상 확보량 계산 보강 | [상세](devlog/2026-05-14/188-images-management-ux-capacity-delete-estimate.md) |
| 2026-05-14 | 189 | Docker prune 추정 정확도 개선과 위험 정리 버튼 추가 | [상세](devlog/2026-05-14/189-docker-prune-estimate-and-danger-actions.md) |
| 2026-05-14 | 190 | 이미지 정리 버튼 문구 개선과 system prune 제거 | [상세](devlog/2026-05-14/190-image-cleanup-label-system-prune-removal.md) |
| 2026-05-14 | 191 | 로컬 이미지 정리 확인 모달 대상 목록 표시 | [상세](devlog/2026-05-14/191-local-image-confirm-list.md) |
| 2026-05-14 | 192 | 이미지 tar 업로드와 서버 로컬 import 기능 추가 | [상세](devlog/2026-05-14/192-local-image-tar-upload-import.md) |
| 2026-05-14 | 193 | 이미지 tar 업로드 413 차단 회피 | [상세](devlog/2026-05-14/193-local-image-upload-chunked.md) |
| 2026-05-14 | 194 | 이미지 tar chunk 업로드 롤백 | [상세](devlog/2026-05-14/194-local-image-upload-single-request-rollback.md) |
| 2026-05-14 | 195 | 서비스 백업 Harbor 설치 설정과 실패 상태 보존 수정 | [상세](devlog/2026-05-14/195-backup-harbor-install-logic-fix.md) |
| 2026-05-14 | 196 | 백업 시스템 설치 진행 로그와 설정 화면 단순화 | [상세](devlog/2026-05-14/196-backup-install-progress-simplified-ui.md) |
| 2026-05-14 | 197 | 자동 백업 UI 개선과 실제 백업 기능 검증 | [상세](devlog/2026-05-14/197-backup-policy-ui-functional-verification.md) |
| 2026-05-14 | 198 | 백업 레지스트리 insecure registry 노드 자동 적용 | [상세](devlog/2026-05-14/198-backup-insecure-registry-node-setup.md) |
| 2026-05-14 | 199 | 이미지 관리 Harbor 컴팩트 UI 재구성 | [상세](devlog/2026-05-14/199-harbor-compact-ui-redesign.md) |
| 2026-05-14 | 200 | 이미지 관리 서버 로컬 저장소 UI 통일 | [상세](devlog/2026-05-14/200-local-image-ui-unification.md) |
| 2026-05-14 | 201 | 서비스 AI MCP scope와 백그라운드 모달 개선 | [상세](devlog/2026-05-14/201-service-ai-runtime-mcp-modal.md) |
| 2026-05-14 | 202 | 서비스 AI 검사 모달 모델 선택 배치 조정 | [상세](devlog/2026-05-14/202-service-ai-modal-model-placement.md) |
| 2026-05-14 | 203 | 서비스 certbot SSL 적용 타이밍과 갱신 관리 보강 | [상세](devlog/2026-05-14/203-service-certbot-runtime-renewal.md) |
| 2026-05-14 | 204 | 서비스 생성 AI Gemini 커스텀 Codex 완료와 진행 표시 수정 | [상세](devlog/2026-05-14/204-service-create-ai-gemini-progress-heartbeat.md) |
| 2026-05-15 | 205 | Docker Infra 운영 배포 installer와 설치 문서 추가 | [상세](devlog/2026-05-15/205-docker-infra-deployment-installer.md) |
| 2026-05-15 | 206 | 초기 설정 마법사를 installer로 통합하고 access 화면 단순화 | [상세](devlog/2026-05-15/206-installer-owned-initial-setup.md) |
| 2026-05-15 | 207 | installer 단독 payload와 설치 관리자 self-cleanup 추가 | [상세](devlog/2026-05-15/207-self-contained-installer-payload-cleanup.md) |
| 2026-05-15 | 208 | custom Codex CLI를 installer binary payload로 전환 | [상세](devlog/2026-05-15/208-codex-cli-binary-payload.md) |
| 2026-05-15 | 209 | installer에 Node.js LTS와 공식 Codex npm 설치 단계 추가 | [상세](devlog/2026-05-15/209-official-codex-npm-installer-step.md) |
| 2026-05-15 | 210 | installer 진행 단계별 file artifact cleanup script 추가 | [상세](devlog/2026-05-15/210-installer-file-artifact-cleanup-script.md) |
| 2026-05-15 | 211 | installer token 제거와 단계형 wizard UI 적용 | [상세](devlog/2026-05-15/211-installer-tokenless-wizard-ui.md) |
| 2026-05-15 | 212 | installer 관리자 비밀번호 단계 보강과 시스템 General 비밀번호 변경 추가 | [상세](devlog/2026-05-15/212-admin-password-general-and-installer-bundle.md) |
| 2026-05-15 | 213 | installer 단계 종료 성공/실패 인지 보강 | [상세](devlog/2026-05-15/213-installer-step-finished-status.md) |
| 2026-05-15 | 214 | 공식 Codex와 custom CLI 설치 경로 분리 및 architecture 검증 | [상세](devlog/2026-05-15/214-codex-official-custom-arch-separation.md) |
| 2026-05-15 | 215 | custom Codex 설치 실패 원인 로그 보강 | [상세](devlog/2026-05-15/215-codex-step-failure-diagnostics.md) |
| 2026-05-15 | 216 | custom Codex CLI aarch64 installer payload 추가 | [상세](devlog/2026-05-15/216-codex-aarch64-installer-payload.md) |
| 2026-05-15 | 217 | WIZ service wrapper port와 bundle 인자 순서 수정 | [상세](devlog/2026-05-15/217-wiz-service-wrapper-port-bundle-order.md) |
| 2026-05-15 | 218 | 서비스 AI 사용 가능 조건과 Codex 브라우저 로그인 추가 | [상세](devlog/2026-05-15/218-service-ai-availability-and-codex-device-login.md) |
| 2026-05-15 | 219 | Codex 브라우저 로그인 PTY 처리와 Compose Monaco 편집 개선 | [상세](devlog/2026-05-15/219-codex-device-login-pty-and-compose-monaco.md) |
| 2026-05-15 | 220 | installer WIZ bundle payload 갱신 관리 스크립트 추가 | [상세](devlog/2026-05-15/220-installer-wiz-bundle-update-script.md) |
| 2026-05-15 | 221 | WIZ root bundle 업데이트 스크립트 단순화 | [상세](devlog/2026-05-15/221-remote-wiz-service-bundle-update.md) |
| 2026-05-17 | 222 | DDNS Edge 서버 분리 등록 흐름 추가 | [상세](devlog/2026-05-17/222-ddns-edge-gateway.md) |
| 2026-05-18 | 223 | DDNS 스키마 미적용 시 도메인 관리 화면 복구 | [상세](devlog/2026-05-18/223-domain-ddns-schema-pending-fallback.md) |
| 2026-05-18 | 224 | DDNS API 등록을 와일드카드 프록시 suffix 방식으로 전환 | [상세](devlog/2026-05-18/224-wildcard-proxy-domain-suffix.md) |
| 2026-05-18 | 225 | 중간 DDNS 관리 시스템 API 등록 방식 복원 | [상세](devlog/2026-05-18/225-ddns-management-api-registration.md) |
| 2026-05-18 | 226 | DDNS 서버 등록 모달 입력 항목 단순화 | [상세](devlog/2026-05-18/226-ddns-modal-api-url-simplification.md) |
| 2026-05-18 | 227 | DDNS update API와 NetworkManager dispatcher 반영 | [상세](devlog/2026-05-18/227-ddns-update-api-networkmanager-dispatcher.md) |
| 2026-05-18 | 228 | DDNS dispatcher 마지막 요청 표시와 수동 API 호출 추가 | [상세](devlog/2026-05-18/228-ddns-dispatcher-status-and-manual-update.md) |
| 2026-05-18 | 229 | DDNS 테이블 UI와 dispatcher 등록 관리 추가 | [상세](devlog/2026-05-18/229-ddns-table-and-dispatcher-registration.md) |
| 2026-05-18 | 230 | 서비스 AI 생성/검사/수정 DDNS 컨텍스트 보강 | [상세](devlog/2026-05-18/230-service-ai-ddns-context.md) |
| 2026-05-18 | 231 | AI DDNS 자동 등록 권한과 경고 처리 보강 | [상세](devlog/2026-05-18/231-ai-ddns-auto-registration-permission.md) |
| 2026-05-18 | 232 | 런타임 AI DDNS 전환 repair 컨텍스트 보강 | [상세](devlog/2026-05-18/232-runtime-ai-ddns-repair-context.md) |
| 2026-05-18 | 233 | DDNS 런타임 AI Codex 실패 fallback 추가 | [상세](devlog/2026-05-18/233-ddns-runtime-ai-codex-fallback.md) |
| 2026-05-18 | 234 | AI DDNS 수정 직후 등록 API 호출 추가 | [상세](devlog/2026-05-18/234-ai-ddns-immediate-register.md) |
| 2026-05-18 | 235 | Codex MCP 핸드셰이크와 DDNS AI 검증 호출 복구 | [상세](devlog/2026-05-18/235-codex-mcp-handshake-ddns-ai.md) |
| 2026-05-18 | 236 | DDNS 서비스 도메인을 wildcard suffix 하위 hostname으로 보정 | [상세](devlog/2026-05-18/236-ddns-child-hostname-normalization.md) |
| 2026-05-18 | 237 | AI 검사 로그 중복 억제와 DDNS 직접 보정 경로 추가 | [상세](devlog/2026-05-18/237-ai-ddns-direct-repair-and-log-dedupe.md) |
| 2026-05-18 | 238 | Codex 런타임 프롬프트 컨텍스트 축약과 MCP 요약 경로 추가 | [상세](devlog/2026-05-18/238-codex-context-budget-mcp-summary.md) |
| 2026-05-18 | 239 | DDNS API 실패 응답 판정과 POST redirect 처리 수정 | [상세](devlog/2026-05-18/239-ddns-api-response-validation.md) |
| 2026-05-19 | 240 | DB migration SQL을 현재 schema baseline으로 통합 | [상세](devlog/2026-05-19/240-db-sql-current-schema-consolidation.md) |
| 2026-05-19 | 241 | 백업 스냅샷 실행과 push 후 로컬 이미지 정리, 백업 저장소 표기 변경 | [상세](devlog/2026-05-19/241-backup-snapshot-local-cleanup-storage-label.md) |
| 2026-05-19 | 242 | 서비스 상세 스냅샷 백업 버튼과 버전 이력 연동 보강 | [상세](devlog/2026-05-19/242-service-detail-snapshot-backup-version-link.md) |
| 2026-05-19 | 243 | wiki_service 스냅샷 백업 컨테이너 매칭 오류 수정 | [상세](devlog/2026-05-19/243-wiki-service-snapshot-container-match.md) |
| 2026-05-19 | 244 | 서비스/시스템 수동 백업 진행 로그 표시 추가 | [상세](devlog/2026-05-19/244-backup-progress-streaming-ui.md) |
| 2026-05-19 | 245 | 서비스 버전 되돌리기 모달과 스냅샷 우선 적용 개선 | [상세](devlog/2026-05-19/245-service-rollback-modal-snapshot-apply.md) |
| 2026-05-19 | 246 | 스냅샷 롤백 적용 시 stack 재생성과 백업 registry 보장 | [상세](devlog/2026-05-19/246-snapshot-rollback-stack-recreate.md) |
| 2026-05-19 | 247 | 스냅샷 롤백 배포 전 백업 저장소 Docker login 추가 | [상세](devlog/2026-05-19/247-snapshot-rollback-registry-login.md) |
| 2026-05-19 | 248 | 롤백 배포 직후 서비스 상세 재조회 오류 방지 | [상세](devlog/2026-05-19/248-rollback-deploy-detail-reload-guard.md) |
| 2026-05-19 | 249 | 롤백 전 백업 저장소 부분 기동 감지와 자동 시작 추가 | [상세](devlog/2026-05-19/249-rollback-backup-registry-startup.md) |
| 2026-05-19 | 250 | 롤백 배포 완료 직전 metadata datetime 직렬화 오류 수정 | [상세](devlog/2026-05-19/250-rollback-deploy-metadata-serialization.md) |
| 2026-05-19 | 251 | 서비스 관리 상태 표시와 적용 버튼 문구 정리 | [상세](devlog/2026-05-19/251-service-management-status-label-cleanup.md) |
| 2026-05-19 | 252 | 서비스 상세 헤더 버튼 정리와 스냅샷 백업 위치 이동 | [상세](devlog/2026-05-19/252-service-header-actions-cleanup.md) |
| 2026-05-19 | 253 | 서비스 버전 이력을 수동 릴리즈 전용으로 전환 | [상세](devlog/2026-05-19/253-service-manual-release-version-policy.md) |
| 2026-05-19 | 254 | 서비스 상세 서버 표시를 Docker Infra 등록 정보 기준으로 보정 | [상세](devlog/2026-05-19/254-service-detail-registered-server-label.md) |
| 2026-05-19 | 255 | 서비스 상세 서버 요약에서 서버 상세 링크 추가 | [상세](devlog/2026-05-19/255-service-detail-server-link.md) |
| 2026-05-19 | 256 | 서비스 상세 상단 서버 버튼 배치와 요약 카드 제거 | [상세](devlog/2026-05-19/256-service-detail-header-server-button.md) |
| 2026-05-19 | 257 | 이미지 삭제 진행 표시와 로컬 서버 전환 로딩 개선 | [상세](devlog/2026-05-19/257-images-delete-loading-local-switch.md) |
| 2026-05-19 | 258 | 이미지 관리 로컬 저장소 서버별 화면 캐시 추가 | [상세](devlog/2026-05-19/258-images-local-node-cache.md) |
| 2026-05-19 | 259 | 서버 관리 일반 서버 등록 해제와 원격 정리 흐름 추가 | [상세](devlog/2026-05-19/259-server-unregister-cleanup-flow.md) |
| 2026-05-19 | 260 | 서버 등록 해제 전 실행 중 서비스 차단 추가 | [상세](devlog/2026-05-19/260-server-unregister-running-service-guard.md) |
| 2026-05-19 | 261 | custom Codex 실행 경로 제거와 provider 직접 API 호출 전환 | [상세](devlog/2026-05-19/261-custom-codex-removal-direct-api.md) |
| 2026-05-19 | 262 | 시스템 설정에 공식 Codex CLI npm 업데이트 기능 추가 | [상세](devlog/2026-05-19/262-codex-cli-npm-update.md) |
| 2026-05-19 | 263 | 마스터 공인 IP와 노드 접근용 사설 IP 분리 | [상세](devlog/2026-05-19/263-master-public-private-ip-split.md) |
| 2026-05-19 | 264 | 서버 관리 중심 서버 IP 표시와 상단 버튼 정리 | [상세](devlog/2026-05-19/264-server-management-header-ip-label.md) |
| 2026-05-19 | 265 | 중심 서버 기본 사설 IP 적용과 표시 보정 | [상세](devlog/2026-05-19/265-local-master-default-private-ip.md) |
| 2026-05-19 | 266 | 서비스 스냅샷 기반 서버 마이그레이션 추가 | [상세](devlog/2026-05-19/266-service-migration-snapshot-redeploy.md) |
| 2026-05-19 | 267 | 서비스 마이그레이션 대상 서버 목록 로딩 수정 | [상세](devlog/2026-05-19/267-service-migration-node-list.md) |
| 2026-05-19 | 268 | Keycloak 실마이그레이션 검증과 백업 레지스트리 보정 | [상세](devlog/2026-05-19/268-keycloak-migration-browser-validation.md) |
| 2026-05-20 | 269 | named volume 별도 이관 로직과 서비스 마이그레이션 연동 | [상세](devlog/2026-05-20/269-service-volume-migration.md) |
| 2026-05-20 | 270 | Keycloak named volume 마이그레이션 실검증 | [상세](devlog/2026-05-20/270-keycloak-volume-migration-validation.md) |
| 2026-05-20 | 271 | 서비스 상세 서버 바로가기 버튼 위치와 새로고침 버튼 정리 | [상세](devlog/2026-05-20/271-service-detail-server-shortcut-placement.md) |
| 2026-05-20 | 272 | 대시보드 서비스 목록 카드와 실행 경고 표시 추가 | [상세](devlog/2026-05-20/272-dashboard-service-alert-card.md) |
| 2026-05-20 | 273 | 실제 사용 DB schema 기준으로 unused table 정리 | [상세](devlog/2026-05-20/273-db-actual-schema-cleanup.md) |
| 2026-05-20 | 274 | 실제 DB에 schema cleanup migration 적용 | [상세](devlog/2026-05-20/274-db-actual-schema-apply.md) |
| 2026-05-20 | 275 | 파일 기반 Compose 템플릿 관리와 서비스 생성 템플릿 적용 흐름 추가 | [상세](devlog/2026-05-20/275-compose-template-feature.md) |
| 2026-05-20 | 276 | Compose 템플릿 seed 파일 직렬화 오류 수정과 브라우저 검증 | [상세](devlog/2026-05-20/276-compose-template-seed-serialization-fix.md) |
| 2026-05-20 | 277 | Compose 템플릿 Monaco editor 재렌더링 방지 | [상세](devlog/2026-05-20/277-template-monaco-stable-options.md) |
| 2026-05-20 | 278 | 템플릿 관리 상세 로딩 캐시와 README 중심 입력 흐름 적용 | [상세](devlog/2026-05-20/278-template-management-readme-tags-cache.md) |
| 2026-05-20 | 279 | 템플릿 관리 AI 초안 생성 흐름 추가 | [상세](devlog/2026-05-20/279-template-management-ai-draft.md) |
| 2026-05-20 | 280 | 템플릿 AI MCP/표준/허용 범위 명시 | [상세](devlog/2026-05-20/280-template-ai-policy-scope.md) |
| 2026-05-20 | 281 | 템플릿 편집 AI 버튼과 탭별 표준 안내 UX 개선 | [상세](devlog/2026-05-20/281-template-ai-edit-tab-guidance.md) |
| 2026-05-20 | 282 | 새 템플릿 작성 방식 선택과 clone 기반 생성 UX 추가 | [상세](devlog/2026-05-20/282-template-create-mode-clone-flow.md) |
| 2026-05-20 | 283 | 서비스 생성 방식 선택 UX와 중복 입력 노출 정리 | [상세](devlog/2026-05-20/283-service-create-mode-selector.md) |
| 2026-05-20 | 284 | 서비스 관리와 생성 화면 초기 로딩 경량화 | [상세](devlog/2026-05-20/284-service-management-fast-load.md) |
| 2026-05-20 | 285 | 템플릿 관리 화면 목록 API 경량화와 상세 지연 로딩 적용 | [상세](devlog/2026-05-20/285-template-management-fast-load.md) |
| 2026-05-20 | 286 | 템플릿 상세 표준 안내 카드를 Monaco 좌측 패널로 재배치 | [상세](devlog/2026-05-20/286-template-detail-guide-left-panel.md) |
| 2026-05-20 | 287 | 템플릿 삭제 후 목록 재조회 제거와 프론트 목록 갱신 적용 | [상세](devlog/2026-05-20/287-template-delete-local-list-update.md) |
| 2026-05-20 | 288 | 서비스 생성 화면 서비스명 입력 위치와 AI 안내 카드 정리 | [상세](devlog/2026-05-20/288-service-create-name-ai-card-layout.md) |
| 2026-05-20 | 289 | 검색 select 드롭다운 overflow clipping 방지 | [상세](devlog/2026-05-20/289-search-select-dropdown-fixed-position.md) |
| 2026-05-20 | 290 | 각 화면 초기 표시 로딩 보강과 템플릿 API 캐시 추가 | [상세](devlog/2026-05-20/290-screen-api-ui-loading-performance.md) |
| 2026-05-20 | 291 | README/라이선스/installer 공개 준비 | [상세](devlog/2026-05-20/291-readme-license-installer-public-prep.md) |
| 2026-05-21 | 292 | 서비스 생성 배포 진행 상태 UX 개선 | [상세](devlog/2026-05-21/292-service-create-deploy-progress-ux.md) |
| 2026-05-21 | 293 | 서비스 상세 Compose 원문 재적용과 nginx 설정 미리보기 보강 | [상세](devlog/2026-05-21/293-service-detail-compose-nginx-apply.md) |
| 2026-05-21 | 294 | DDNS/일반 도메인과 노드 토폴로지별 nginx 자동 생성 보강 | [상세](devlog/2026-05-21/294-nginx-domain-node-topology.md) |
| 2026-05-21 | 295 | 서비스 수정 모달 즉시 표시와 DDNS 삭제 실패 내성 보강 | [상세](devlog/2026-05-21/295-service-edit-modal-delete-ddns.md) |
| 2026-05-21 | 296 | 템플릿 생성 도메인/DDNS/nginx 플로우 점검과 DDNS 매칭 실패 보강 | [상세](devlog/2026-05-21/296-template-domain-nginx-flow-check.md) |
| 2026-05-21 | 297 | 기본 템플릿 삭제 후 재생성 방지 | [상세](devlog/2026-05-21/297-template-delete-seed-persistence.md) |
| 2026-05-21 | 298 | 템플릿 저장 후 목록 재조회 제거 | [상세](devlog/2026-05-21/298-template-save-local-list-update.md) |
| 2026-05-21 | 299 | wiz_dev 템플릿 DDNS 실생성 검증과 배치/검증 오류 보강 | [상세](devlog/2026-05-21/299-wiz-dev-ddns-browser-create-test.md) |
| 2026-05-21 | 300 | 서비스 상세 느린 부가 정보 API 분리 | [상세](devlog/2026-05-21/300-service-detail-api-extras-split.md) |
| 2026-05-21 | 301 | 템플릿 상세 화면 API 초기화 경량화와 브라우저 속도 검증 | [상세](devlog/2026-05-21/301-template-detail-api-fast-path.md) |
| 2026-05-21 | 302 | 서비스 상세 fast path와 AI 옵션 지연 로딩 적용 | [상세](devlog/2026-05-21/302-service-detail-fast-path-ai-lazy-load.md) |
| 2026-05-21 | 303 | 서비스 생성 다음 버튼을 생성 방식별 주 동작과 연결 | [상세](devlog/2026-05-21/303-service-create-next-primary-action.md) |
| 2026-05-21 | 304 | DDNS SSL 와일드카드 매칭과 certbot fallback 보강 | [상세](devlog/2026-05-21/304-ddns-ssl-wildcard-certbot-fallback.md) |
| 2026-05-22 | 001 | 서비스 컨테이너 웹 터미널 exec 기능 추가 | [상세](devlog/2026-05-22/001-service-container-terminal-exec.md) |
| 2026-05-27 | 001 | Compose/Nginx 탭 서비스 예외 응답 보강 | [상세](devlog/2026-05-27/001-compose-nginx-service-error-response.md) |
| 2026-05-27 | 002 | Compose healthcheck 필수 검증 제거 | [상세](devlog/2026-05-27/002-compose-healthcheck-optional.md) |
| 2026-05-28 | 001 | 최신 기능 반영 installer WIZ bundle payload 갱신 | [상세](devlog/2026-05-28/001-installer-wiz-bundle-refresh.md) |
| 2026-05-28 | 002 | 원격 서버 최신 Docker Infra 재설치 | [상세](devlog/2026-05-28/002-remote-server-reinstall.md) |
| 2026-05-28 | 003 | AI 기능 Agent 기반 재정리 | [상세](devlog/2026-05-28/003-ai-agent-runtime-refactor.md) |
| 2026-05-28 | 004 | Docker Infra MCP Agent 권한 계약 상세화 | [상세](devlog/2026-05-28/004-mcp-agent-permission-contract.md) |
| 2026-05-28 | 005 | AI Agent CLI 설치를 시스템 설정 실행 방식으로 전환 | [상세](devlog/2026-05-28/005-agent-cli-system-settings-install.md) |
| 2026-05-28 | 006 | AI Agent 설정 화면 단순화 | [상세](devlog/2026-05-28/006-ai-agent-settings-simplification.md) |
| 2026-05-29 | 001 | Codex 설정 문단형 UI와 업그레이드 셸 수정 | [상세](devlog/2026-05-29/001-codex-settings-ui-upgrade-shell.md) |
| 2026-05-29 | 002 | AI Agent 설정 버튼 좌측 정렬 | [상세](devlog/2026-05-29/002-ai-agent-button-left-alignment.md) |
| 2026-05-29 | 003 | AI Agent 설정 저장 버튼과 진행 로그 UI 정리 | [상세](devlog/2026-05-29/003-ai-agent-save-button-log-ui.md) |
| 2026-05-29 | 004 | AI Agent 버전 확인 저장과 공통 업그레이드 버튼 추가 | [상세](devlog/2026-05-29/004-ai-agent-update-cache-common-buttons.md) |
| 2026-05-29 | 005 | Claude Code Agent 네이티브 설치 전환 | [상세](devlog/2026-05-29/005-claude-code-native-install.md) |
| 2026-05-29 | 006 | Claude Code 설치 스크립트 문구 롤백과 기존 설치 정리 | [상세](devlog/2026-05-29/006-claude-code-install-script-wording.md) |
| 2026-05-29 | 007 | Hermes Agent 설치 스크립트 방식 전환 | [상세](devlog/2026-05-29/007-hermes-agent-install-script.md) |
| 2026-05-29 | 008 | Agent 설치 스크립트 완료 상태 갱신 지연 수정 | [상세](devlog/2026-05-29/008-agent-install-doctor-hang.md) |
| 2026-05-29 | 009 | Claude/Hermes 설치 후 액션 정책과 웹 설정 보강 | [상세](devlog/2026-05-29/009-agent-login-upgrade-hermes-settings.md) |
| 2026-05-29 | 010 | Claude 자동 업데이트 UI와 Hermes API Key 설정 단순화 | [상세](devlog/2026-05-29/010-agent-settings-ui-simplification.md) |
| 2026-05-29 | 011 | AI Agent 모델 목록 공식 출처 연동과 검색 Select 적용 | [상세](devlog/2026-05-29/011-agent-model-catalog-search-select.md) |
| 2026-05-29 | 012 | 다중 AI Agent 기본 선택 설정 추가 | [상세](devlog/2026-05-29/012-ai-agent-default-selection.md) |
| 2026-05-29 | 013 | 전역 AI Agent 플로팅 채팅 추가 | [상세](devlog/2026-05-29/013-ai-agent-floating-chat.md) |
| 2026-05-29 | 014 | AI Agent 다단 도킹 패널과 Hermes 런타임 설정 보강 | [상세](devlog/2026-05-29/014-ai-agent-dock-hermes-runtime.md) |
| 2026-05-29 | 015 | AI Agent 스트리밍 채팅 UI 정리 | [상세](devlog/2026-05-29/015-ai-agent-streaming-chat-ui.md) |
| 2026-05-29 | 016 | AI Agent 스트림 멈춤과 빈 응답 표시 보강 | [상세](devlog/2026-05-29/016-ai-agent-stream-timeout-empty-response.md) |
| 2026-05-29 | 017 | AI Agent 패널 리사이즈와 Hermes 빈 응답 재시도 보강 | [상세](devlog/2026-05-29/017-ai-agent-resize-context-hermes-retry.md) |
| 2026-05-29 | 016 | 주요 화면 상세 상태 URL 라우팅 명시화 | [상세](devlog/2026-05-29/016-explicit-detail-routing.md) |
| 2026-05-29 | 018 | AI Agent 채팅 응답 Markdown 렌더링 적용 | [상세](devlog/2026-05-29/018-ai-agent-markdown-rendering.md) |
| 2026-05-29 | 019 | AI Agent Markdown 테이블과 후속 동작 버튼 추가 | [상세](devlog/2026-05-29/019-ai-agent-table-suggested-actions.md) |
| 2026-06-01 | 001 | AI Agent 사이드바 채팅 구조와 응답/동작 정책 개선 | [상세](devlog/2026-06-01/001-ai-agent-sidebar-response-action-policy.md) |
| 2026-06-01 | 002 | AI Agent 히스토리 저장·다운로드·삭제 관리 추가 | [상세](devlog/2026-06-01/002-ai-agent-history-management.md) |
| 2026-06-01 | 003 | AI Agent 버튼 즉시 표시와 로딩 상태 패널 추가 | [상세](devlog/2026-06-01/003-ai-agent-loading-toggle.md) |
| 2026-06-01 | 004 | AI Agent 응답 시간과 히스토리 상세 표시 개선 | [상세](devlog/2026-06-01/004-ai-agent-duration-history-detail.md) |
| 2026-06-01 | 005 | AI Agent Markdown 렌더링과 히스토리 상세 복사 UX 개선 | [상세](devlog/2026-06-01/005-ai-agent-markdown-history-copy.md) |
| 2026-06-01 | 006 | AI Agent 화면 제어 액션과 서버 상태 매크로 생성 명령 연결 | [상세](devlog/2026-06-01/006-ai-agent-page-control-macro-action.md) |
| 2026-06-01 | 007 | Swagger 기반 AI Agent 메뉴별 API 작업 카탈로그와 실행 액션 연결 | [상세](devlog/2026-06-01/007-ai-agent-openapi-operation-catalog.md) |
| 2026-06-01 | 008 | AI Agent 렌더 루프 방지와 코드블럭/히스토리 상세 사이드바 개선 | [상세](devlog/2026-06-01/008-ai-agent-render-code-history-detail.md) |
| 2026-06-01 | 009 | AI Agent 동적 코드블럭 스타일 적용과 히스토리 다음 동작 설명 제거 | [상세](devlog/2026-06-01/009-ai-agent-deep-codeblock-action-description.md) |
| 2026-06-01 | 010 | AI Agent 코드블럭 강조선 제거와 히스토리 페이지네이션 추가 | [상세](devlog/2026-06-01/010-ai-agent-history-pagination-codeblock-border.md) |
| 2026-06-01 | 011 | AI Agent 도킹 중 서버 화면 레이아웃과 상세 탭 라우팅 재사용 개선 | [상세](devlog/2026-06-01/011-layout-route-reuse.md) |
| 2026-06-01 | 012 | AI Agent TODO 기반 순차 실행과 마스터 노드 매크로 실행 연결 | [상세](devlog/2026-06-01/012-ai-agent-todo-sequential-macro-run.md) |
| 2026-06-01 | 013 | AI Agent 세션 기반 대화 지속과 히스토리 그룹화 추가 | [상세](devlog/2026-06-01/013-ai-agent-session-continuation.md) |
| 2026-06-01 | 014 | AI Agent TODO 패널과 계획 후 TODO별 실행 흐름 분리 | [상세](devlog/2026-06-01/014-ai-agent-todo-panel-planned-flow.md) |
| 2026-06-01 | 015 | AI Agent stream/fallback 히스토리 중복 기록 방지 | [상세](devlog/2026-06-01/015-ai-agent-history-request-id-dedupe.md) |
| 2026-06-01 | 016 | AI Agent 스트림 응답 대기 시간 10분 확장 | [상세](devlog/2026-06-01/016-ai-agent-stream-timeout-10min.md) |
| 2026-06-01 | 017 | AI Agent TODO 목록 표시 간소화와 우측 잘림 보정 | [상세](devlog/2026-06-01/017-ai-agent-todo-list-cleanup.md) |
| 2026-06-01 | 018 | AI Agent 히스토리 세션 이어서 대화와 선택 중 렌더 지연 | [상세](devlog/2026-06-01/018-ai-agent-history-continue-selection-render.md) |
| 2026-06-02 | 001 | AI Agent 실행 카탈로그 확장과 확인 후 destructive 실행 보완 | [상세](devlog/2026-06-02/001-ai-agent-capability-coverage.md) |
| 2026-06-02 | 002 | AI Agent API 액션 체이닝과 템플릿 서비스 생성 검증 | [상세](devlog/2026-06-02/002-ai-agent-template-service-flow.md) |
| 2026-06-02 | 003 | AI Agent MCP 액션 카탈로그와 진행 스트리밍 개선 | [상세](devlog/2026-06-02/003-ai-agent-mcp-action-progress.md) |
| 2026-06-04 | 001 | 서비스 host-mode 포트 변경 배포 실패 수정 | [상세](devlog/2026-06-04/001-service-host-port-update-order.md) |
| 2026-06-04 | 002 | bus 서비스 host-mode 포트 보정 배포 | [상세](devlog/2026-06-04/002-bus-service-host-port-redeploy.md) |
| 2026-06-04 | 003 | bus 서비스 SSL 인증서 발급과 DNS 전파 대기 보강 | [상세](devlog/2026-06-04/003-bus-service-ssl-certificate-dns-wait.md) |
| 2026-06-08 | 001 | AI Agent 진행 로그만 남는 응답 표시 회귀 수정 | [상세](devlog/2026-06-08/001-ai-agent-progress-only-response-fix.md) |
| 2026-06-08 | 002 | AI Agent 빈 채팅의 이전 세션 재사용 방지 | [상세](devlog/2026-06-08/002-ai-agent-new-chat-session-isolation.md) |
| 2026-06-08 | 003 | AI Agent 진행 요약 스트리밍과 완료 이벤트 처리 재정비 | [상세](devlog/2026-06-08/003-ai-agent-thinking-stream-final-response.md) |
| 2026-06-08 | 004 | AI Agent SSE read race로 최종 응답 누락되는 문제 수정 | [상세](devlog/2026-06-08/004-ai-agent-sse-read-race-fix.md) |
| 2026-06-08 | 004 | AI Agent 응답 Markdown 테이블 디자인 적용 | [상세](devlog/2026-06-08/004-ai-agent-markdown-table-design.md) |
| 2026-06-08 | 005 | AI Agent 패널 width 로컬 스토리지 보존 | [상세](devlog/2026-06-08/005-ai-agent-width-local-storage.md) |
| 2026-06-08 | 006 | AI Agent 응답 텍스트 드래그 선택 유지 보강 | [상세](devlog/2026-06-08/006-ai-agent-selection-preserve.md) |
| 2026-06-08 | 007 | AI Agent 히스토리 목록 텍스트 드래그 선택 보강 | [상세](devlog/2026-06-08/007-ai-agent-history-list-selection.md) |
| 2026-06-08 | 008 | AI Agent 히스토리 turn 카드 드래그 선택 보강 | [상세](devlog/2026-06-08/008-ai-agent-history-turn-selection.md) |
| 2026-06-08 | 009 | 서비스 생성 템플릿 단일 흐름 단순화 | [상세](devlog/2026-06-08/009-service-create-template-only-flow.md) |
| 2026-06-08 | 010 | 도메인 관리를 DDNS 전용 흐름으로 단순화 | [상세](devlog/2026-06-08/010-ddns-only-domain-management.md) |
| 2026-06-08 | 011 | AI Agent 실행 후 현재 화면 API 재호출 추가 | [상세](devlog/2026-06-08/011-ai-agent-current-screen-refresh.md) |
| 2026-06-08 | 012 | AI 템플릿 생성 공개 포트 매핑 규칙 보강 | [상세](devlog/2026-06-08/012-ai-template-public-port-policy.md) |
| 2026-06-08 | 013 | DDNS 도메인 관리 표 컬럼과 서비스 연결 정보 개선 | [상세](devlog/2026-06-08/013-ddns-domain-table-service-link.md) |
| 2026-06-08 | 014 | 서비스 생성 화면 디자인 통일성 보강 | [상세](devlog/2026-06-08/014-service-create-design-unification.md) |
| 2026-06-08 | 015 | DDNS 도메인 표 정렬과 링크 아이콘 UI 보강 | [상세](devlog/2026-06-08/015-ddns-domain-table-link-icons.md) |
| 2026-06-08 | 016 | DDNS 레코드 Hostname 외부 링크 아이콘 추가 | [상세](devlog/2026-06-08/016-ddns-hostname-external-link-icon.md) |
| 2026-06-08 | 017 | 서비스 생성 레이아웃 재정리와 DDNS 기본 활성화 | [상세](devlog/2026-06-08/017-service-create-layout-domain-default.md) |
| 2026-06-08 | 018 | 서비스 생성 세로 흐름과 README 팝오버 적용 | [상세](devlog/2026-06-08/018-service-create-vertical-flow-readme-popover.md) |
| 2026-06-09 | 001 | 서비스 생성 화면 폭과 템플릿 변수 UX 보정 | [상세](devlog/2026-06-09/001-service-create-width-template-field-ux.md) |
| 2026-06-09 | 002 | 관리 화면 보드형 레이아웃과 공통 페이지네이션 적용 | [상세](devlog/2026-06-09/002-management-board-pagination.md) |
| 2026-06-09 | 003 | 서비스 생성 비밀 값 표시 토글 추가 | [상세](devlog/2026-06-09/003-service-create-secret-visibility-toggle.md) |
| 2026-06-09 | 004 | 관리 화면 목록/상세 렌더링 완전 분리 | [상세](devlog/2026-06-09/004-management-list-detail-separation.md) |
| 2026-06-09 | 005 | 관리 목록 row 클릭 이동과 상세 헤더 정리 | [상세](devlog/2026-06-09/005-management-row-click-detail-header.md) |
| 2026-06-09 | 006 | 로그인 이후 콘솔 디자인 리프레시 | [상세](devlog/2026-06-09/006-console-design-refresh.md) |
| 2026-06-09 | 007 | 콘솔 UI 전수 점검과 select/작업 로그/도메인 레이아웃 보정 | [상세](devlog/2026-06-09/007-console-ui-audit-select-operation-domain.md) |
| 2026-06-09 | 008 | 시스템 설정 load API 1초 미만 응답으로 경량화 | [상세](devlog/2026-06-09/008-system-load-fast-response.md) |
| 2026-06-09 | 009 | 서비스 수정 모달 기본/고급 분리와 빠른 기본 저장 경로 추가 | [상세](devlog/2026-06-09/009-service-edit-modal-basic-advanced.md) |
| 2026-06-10 | 001 | AI Agent 런타임 진행 스트리밍과 TODO 계획 생성 개선 | [상세](devlog/2026-06-10/001-ai-agent-runtime-streaming-todo-plan.md) |
| 2026-06-10 | 002 | 서비스 상세 서버 바로가기 배치 서버 fallback 보강 | [상세](devlog/2026-06-10/002-service-detail-server-shortcut-fallback.md) |
| 2026-06-10 | 003 | 서비스 상세 컨테이너 컨텍스트 메뉴 레이어 보정 | [상세](devlog/2026-06-10/003-service-container-context-menu-layer.md) |
| 2026-06-10 | 004 | 서비스 상세 컨테이너 메뉴 상위 stacking context 보강 | [상세](devlog/2026-06-10/004-service-container-menu-stacking-context.md) |
| 2026-06-10 | 004 | 서비스 파일 트리와 컨테이너 내부 파일 관리 통합 | [상세](devlog/2026-06-10/004-service-file-tree-container-files.md) |
| 2026-06-10 | 005 | 서비스 상세 컨테이너 로그 스트리밍 메뉴 추가 | [상세](devlog/2026-06-10/005-service-container-log-stream-menu.md) |
| 2026-06-10 | 006 | 서비스 생성 Compose 내부 DB host namespace 보정 | [상세](devlog/2026-06-10/006-service-compose-internal-host-qualification.md) |
| 2026-06-10 | 007 | 서비스 목록에 실행 서버 정보 표시 | [상세](devlog/2026-06-10/007-service-list-runtime-server-summary.md) |
| 2026-06-10 | 008 | 서비스 파일/컨테이너 파일 탭 브라우저 검증 기반 레이아웃 보정 | [상세](devlog/2026-06-10/008-service-file-layout-browser-polish.md) |
| 2026-06-10 | 009 | 컨테이너 로그를 터미널이 아닌 전용 로그 뷰어로 분리 | [상세](devlog/2026-06-10/009-service-container-log-viewer-separation.md) |
| 2026-06-10 | 010 | 서비스 수정 고급 모드 탭 레이아웃 정리 | [상세](devlog/2026-06-10/010-service-edit-advanced-layout-polish.md) |
| 2026-06-10 | 011 | mini3 런타임 서비스 Compose DB host 보정 적용 | [상세](devlog/2026-06-10/011-mini3-runtime-compose-db-host-apply.md) |
| 2026-06-10 | 012 | 서비스 디렉터리 전체 조작 UI와 컨테이너 루트 파일 목록 보정 | [상세](devlog/2026-06-10/012-service-directory-full-file-controls-container-root.md) |
| 2026-06-10 | 013 | 서비스 컨테이너 로그 조회를 API 폴링 방식으로 분리 | [상세](devlog/2026-06-10/013-service-container-log-api-polling.md) |
| 2026-06-10 | 014 | 서비스 수정 구성 탭 연결 포트 컬럼 여백 축소 | [상세](devlog/2026-06-10/014-service-edit-components-port-column-width.md) |
| 2026-06-10 | 015 | 파일 트리 compact 아이콘 모드와 컨테이너 전환 race 보정 | [상세](devlog/2026-06-10/015-file-tree-compact-icons-container-switch-race.md) |
| 2026-06-10 | 016 | 서비스 수정 구성 탭 포트 추가 버튼 아이콘화 | [상세](devlog/2026-06-10/016-service-edit-port-add-icon-button.md) |
| 2026-06-10 | 017 | 명함관리 app 중지 컨테이너 기반 복구 이미지 적용 | [상세](devlog/2026-06-10/017-business-card-app-container-recovery.md) |
| 2026-06-10 | 018 | 컨테이너 내부 파일 탭 실행 중 컨테이너만 표시 | [상세](devlog/2026-06-10/018-container-file-running-only.md) |
| 2026-06-10 | 019 | AI Agent 단순 질문 fast path와 답변 가독성 보강 | [상세](devlog/2026-06-10/019-ai-agent-fast-question-readable-response.md) |
| 2026-06-10 | 020 | AI Agent Codex todo_list 스트림 기반 TODO 적용 | [상세](devlog/2026-06-10/020-ai-agent-codex-todo-list-stream.md) |
| 2026-06-10 | 021 | 서비스 생성 템플릿 변수와 배포 진행 표시 보강 | [상세](devlog/2026-06-10/021-service-create-template-deploy-flow.md) |
| 2026-06-10 | 022 | 관리 화면 헤더/저장 버튼/모달 표시 방식 공통화 | [상세](devlog/2026-06-10/022-ui-consistency-global-modal-actions.md) |
| 2026-06-10 | 023 | AI Agent Claude/Hermes 스트림 TODO/진행 이벤트 연동 | [상세](devlog/2026-06-10/023-ai-agent-claude-hermes-stream-events.md) |
| 2026-06-10 | 024 | 원격 포트 점검 실패 시 로컬 대체 확인 제거 | [상세](devlog/2026-06-10/024-remote-port-check-no-local-substitute.md) |
| 2026-06-10 | 025 | 실제 브라우저 메뉴 순회 기반 UI 액션 정렬 보정 | [상세](devlog/2026-06-10/025-browser-ui-full-menu-consistency.md) |
| 2026-06-10 | 026 | DDNS 관리 서버 표 nowrap과 작업 컬럼 겹침 보정 | [상세](devlog/2026-06-10/026-ddns-table-nowrap-action-overlap.md) |
| 2026-06-10 | 027 | 서비스 상세 콘솔 모달 헤더와 생성 화면 AI 버튼 겹침 보정 | [상세](devlog/2026-06-10/027-service-console-header-ai-toggle-overlap.md) |
| 2026-06-10 | 028 | 컨테이너 파일 미리보기 모달 overflow 보정 | [상세](devlog/2026-06-10/028-container-file-preview-modal-overflow.md) |
| 2026-06-11 | 001 | 서비스 목록 컨테이너 컬럼과 컨테이너 파일 탭 정렬 적용 | [상세](devlog/2026-06-11/001-service-list-container-column-file-sort.md) |
| 2026-06-11 | 002 | 서비스 생성 공개 포트 well-known 자동 할당 회피 | [상세](devlog/2026-06-11/002-service-create-well-known-port-avoidance.md) |
| 2026-06-11 | 003 | 서비스 목록 컨테이너/포트 컬럼 분리 | [상세](devlog/2026-06-11/003-service-list-container-port-columns.md) |
| 2026-06-11 | 004 | DDNS 도메인 관리 UI 컬럼과 등록 레코드 서버 표시 보정 | [상세](devlog/2026-06-11/004-domain-ddns-ui-target-server.md) |
| 2026-06-11 | 005 | 서비스 관리 생성 UI 레이아웃과 필수값 검증 보정 | [상세](devlog/2026-06-11/005-service-management-create-ui-validation.md) |
| 2026-06-11 | 006 | DDNS 관리 서버 컬럼 순서와 등록 레코드 필터 UI 보정 | [상세](devlog/2026-06-11/006-ddns-column-order-registration-filter.md) |
| 2026-06-11 | 007 | 서비스/템플릿 생성 화면 세로 흐름과 레이어 검증 보정 | [상세](devlog/2026-06-11/007-service-template-create-vertical-flow-browser-validation.md) |
| 2026-06-11 | 008 | custom select overlay 복원과 README 버튼 배치 보정 | [상세](devlog/2026-06-11/008-custom-select-overlay-readme-placement.md) |
| 2026-06-11 | 009 | 서비스 생성 README 팝오버 마크다운 렌더링 적용 | [상세](devlog/2026-06-11/009-service-create-readme-markdown-popover.md) |
| 2026-06-11 | 010 | 템플릿 관리 목록과 상세 편집 UI 정리 | [상세](devlog/2026-06-11/010-template-management-ui-polish.md) |
| 2026-06-11 | 011 | 템플릿 목록 생성 화면 노출 컬럼 추가 | [상세](devlog/2026-06-11/011-template-list-enabled-column.md) |
| 2026-06-11 | 012 | 서비스 상세 Compose/Nginx 탭 제거 | [상세](devlog/2026-06-11/012-service-detail-compose-nginx-tab-removal.md) |
| 2026-06-12 | 001 | 서비스 상세 마이그레이션/수정 모달 UX 보정 | [상세](devlog/2026-06-12/001-service-detail-migration-edit-modal-ux.md) |
| 2026-06-12 | 002 | 마이그레이션 모달 custom search-select 유지 보정 | [상세](devlog/2026-06-12/002-migration-custom-search-select-fix.md) |
| 2026-06-12 | 003 | 서버 관리 목록 런타임 수량 컬럼과 설명 문구 정리 | [상세](devlog/2026-06-12/003-server-management-runtime-count-columns.md) |
| 2026-06-12 | 004 | 매크로 화면 통합 실행 패널과 첨부 다운로드 적용 | [상세](devlog/2026-06-12/004-macro-unified-run-panel.md) |
| 2026-06-12 | 005 | 서버 상세 헤더 뱃지 배치 정리 | [상세](devlog/2026-06-12/005-server-detail-header-badges.md) |
| 2026-06-12 | 006 | 매크로 목록 압축과 서비스-컨테이너 선택 분리 | [상세](devlog/2026-06-12/006-macro-compact-list-service-container-select.md) |
| 2026-06-13 | 001 | 매크로 실행 인자 사용 옵션 복원 | [상세](devlog/2026-06-13/001-macro-run-args-option-restore.md) |
| 2026-06-15 | 001 | 로그인 화면 운영 문구와 키워드 카드 개선 | [상세](devlog/2026-06-15/001-access-login-copy-keyword-cards.md) |
| 2026-06-17 | 001 | AI Agent Enter 요청 전송 비활성화 | [상세](devlog/2026-06-17/001-ai-agent-enter-submit-disable.md) |
| 2026-06-17 | 002 | 컨테이너 파일 트리 폴더 다운로드 추가 | [상세](devlog/2026-06-17/002-container-directory-download.md) |
| 2026-06-18 | 001 | 대시보드 서버 상세 이동과 서비스 상태 배지 정리 | [상세](devlog/2026-06-18/001-dashboard-server-detail-service-badge.md) |
| 2026-06-18 | 002 | 대시보드 서버/서비스 목록 행 표시 방식 보정 | [상세](devlog/2026-06-18/002-dashboard-row-link-and-service-domain.md) |
| 2026-06-18 | 003 | 대시보드 서버 목록 제목과 IP 표시 위치 보정 | [상세](devlog/2026-06-18/003-dashboard-server-title-ip-placement.md) |
| 2026-06-18 | 004 | 대시보드 서버 목록 등록 수 표시 적용 | [상세](devlog/2026-06-18/004-dashboard-server-count-summary.md) |
| 2026-06-18 | 005 | Swarm 선택 연동과 Compose 배포 네트워크 분리 | [상세](devlog/2026-06-18/005-swarm-optional-compose-network.md) |
| 2026-06-18 | 006 | Compose 원격 볼륨 삭제 보강과 Swarm/비Swarm smoke 검증 | [상세](devlog/2026-06-18/006-compose-volume-cleanup-smoke-test.md) |
| 2026-06-18 | 007 | 에이전트 작업 중 Compose 볼륨 보존 가드 보강 | [상세](devlog/2026-06-18/007-agent-compose-volume-preservation-guard.md) |
| 2026-06-18 | 008 | 서버 상태 아이콘과 배포 방식 문구 정리 | [상세](devlog/2026-06-18/008-server-status-icon-deployment-labels.md) |
| 2026-06-22 | 001 | 이미지 관리 좌우 레이아웃과 Harbor 프로젝트 삭제 보강 | [상세](devlog/2026-06-22/001-images-layout-harbor-delete-local-load.md) |
| 2026-06-22 | 002 | 시스템 백업 UI와 스냅샷 기본 정책 정리 | [상세](devlog/2026-06-22/002-system-backup-snapshot-ux.md) |
| 2026-06-22 | 003 | 이미지 관리 독립 서버 목록 로드와 Harbor 헤더 액션 정리 | [상세](devlog/2026-06-22/003-images-independent-server-and-harbor-actions.md) |
| 2026-06-22 | 004 | 자동 백업 정책 저장 시 crontab 등록 연결 | [상세](devlog/2026-06-22/004-backup-policy-crontab-sync.md) |
| 2026-06-22 | 005 | 자동 백업 실행 대상 등록 서비스 스냅샷으로 전환 | [상세](devlog/2026-06-22/005-backup-policy-runtime-service-snapshots.md) |
| 2026-06-22 | 006 | 백업 진행 서비스명 표시와 보존 정책 자동 정리 | [상세](devlog/2026-06-22/006-backup-progress-retention-volume-design.md) |
| 2026-06-22 | 007 | 서비스 버전 이력 백업 내역 연동과 만료 복원 차단 | [상세](devlog/2026-06-22/007-service-version-backup-history-restore-guard.md) |
| 2026-06-22 | 008 | named volume 백업 설계 Agent 연동과 ORAS 공급 정책 보강 | [상세](devlog/2026-06-22/008-volume-backup-agent-oras-design.md) |
| 2026-06-22 | 009 | ORAS 필수 정책과 named volume 자동 백업 구현 | [상세](devlog/2026-06-22/009-oras-required-volume-backup-implementation.md) |
| 2026-06-22 | 010 | 서버 등록 해제 시 Swarm 원격 확인과 수집 agent 정리 검증 | [상세](devlog/2026-06-22/010-node-unregister-swarm-monitoring-cleanup.md) |
| 2026-06-22 | 011 | 독립 서버 등록 해제 시 Swarm skip 상태 정상화 | [상세](devlog/2026-06-22/011-node-unregister-standalone-swarm-skip.md) |
| 2026-06-22 | 012 | ORAS absolute path 오류 수정과 named volume 백업 실수행 | [상세](devlog/2026-06-22/012-volume-backup-oras-path-fix-run.md) |
| 2026-06-22 | 013 | 시스템 백업 전체 스냅샷 대상 처리와 버전 이력 체크포인트 연결 | [상세](devlog/2026-06-22/013-system-backup-version-checkpoint-snapshot-limit.md) |
| 2026-06-22 | 014 | 서비스 생성 자동 배치 CPU/Memory 구간 통계 반영 | [상세](devlog/2026-06-22/014-service-placement-resource-window-stats.md) |
| 2026-06-22 | 015 | 시스템 백업 무제한 대상 처리와 기본 백그라운드 실행 | [상세](devlog/2026-06-22/015-system-backup-unbounded-background-polling.md) |
| 2026-06-22 | 016 | 서비스 상세 상태 확인 경량화와 무료 SSL 섹션 로드 보정 | [상세](devlog/2026-06-22/016-service-detail-status-refresh-ssl-section.md) |
| 2026-06-22 | 017 | 서비스 상세 컨테이너 버전 배지 추가 | [상세](devlog/2026-06-22/017-service-container-version-badge.md) |
| 2026-06-22 | 018 | 서비스 컨테이너 메뉴 z-index 보정 | [상세](devlog/2026-06-22/018-service-container-menu-z-index.md) |
| 2026-06-22 | 019 | 컨테이너 버전 배지 digest 대신 태그 표시 | [상세](devlog/2026-06-22/019-service-container-version-tag-parse.md) |
| 2026-06-22 | 020 | 무료 SSL 인증서 상태 표시 데이터 소스 통일 | [상세](devlog/2026-06-22/020-service-free-ssl-status-source.md) |
| 2026-06-22 | 021 | 서비스 상세 구성 탭 AI 검사/수정 버튼 제거 | [상세](devlog/2026-06-22/021-service-detail-remove-ai-repair-button.md) |
| 2026-06-22 | 022 | 서비스 상세 컨테이너별 버전 변경 기능 추가 | [상세](devlog/2026-06-22/022-service-container-version-change.md) |
| 2026-06-22 | 023 | 매크로 다중 스케줄과 cron.d 파일 실행 경로 추가 | [상세](devlog/2026-06-22/023-macro-schedule-crond.md) |
| 2026-06-22 | 024 | 버전 변경 모달 이미지 존재 검증 버튼 추가 | [상세](devlog/2026-06-22/024-service-container-version-image-validation.md) |
| 2026-06-22 | 025 | 이미지 검증 결과 표시 signal 이름 오류 수정 | [상세](devlog/2026-06-22/025-service-container-version-check-signal-fix.md) |
| 2026-06-22 | 026 | 매크로 스케줄 다중 요일 선택과 실행 이력 표시 보정 | [상세](devlog/2026-06-22/026-macro-schedule-weekdays-history.md) |
| 2026-06-22 | 027 | 매크로 스케줄 DB 반영과 대상 목록/첨부 파일 삭제 UX 보정 | [상세](devlog/2026-06-22/027-macro-schedule-db-file-delete-ui.md) |
| 2026-06-22 | 028 | 매크로 첨부 파일 삭제 로컬 갱신과 스케줄 대상 검색 추가 | [상세](devlog/2026-06-22/028-macro-file-local-delete-target-search.md) |
| 2026-06-22 | 028 | ORAS named volume 복원 경로 구현과 레이어 동작 검증 | [상세](devlog/2026-06-22/028-oras-volume-restore-validation.md) |
| 2026-06-22 | 029 | 이미지 검증 Compose 제한 해제와 런타임 image fallback 추가 | [상세](devlog/2026-06-22/029-service-container-version-validate-runtime-image.md) |
| 2026-06-22 | 030 | 버전 변경 적용 전 이미지 검증 필수화 | [상세](devlog/2026-06-22/030-service-container-version-change-requires-validation.md) |
| 2026-06-22 | 031 | 볼륨 백업 장기 레이어형 스토리지 설계 문서화 | [상세](devlog/2026-06-22/031-volume-layered-storage-design.md) |
| 2026-06-22 | 032 | overlay 서비스 버전 변경 적용 경로 보정 | [상세](devlog/2026-06-22/032-service-container-version-swarm-update.md) |
| 2026-06-23 | 001 | 미니PC 지향 볼륨 스토리지 후보와 Ceph 제외 기준 보강 | [상세](devlog/2026-06-23/001-mini-pc-volume-storage-direction.md) |
| 2026-06-23 | 002 | 매크로 스케줄 대상 높이 고정과 실행 이력 결과 펼침 추가 | [상세](devlog/2026-06-23/002-macro-schedule-history-detail-layout.md) |
| 2026-06-23 | 003 | 컨테이너 버전 변경 Compose 네트워크 컨텍스트 보정 | [상세](devlog/2026-06-23/003-service-container-version-compose-network-context.md) |
| 2026-06-23 | 004 | 로그인 세션 지속시간 표시와 설정 저장 추가 | [상세](devlog/2026-06-23/004-session-duration-display-settings.md) |
| 2026-06-23 | 005 | 세션 지속시간 표시 위치를 로그인 화면에서 사이드바로 이동 | [상세](devlog/2026-06-23/005-session-duration-sidebar-display.md) |
| 2026-06-23 | 006 | 사이드바 세션 표시를 설정값에서 남은 시간으로 변경 | [상세](devlog/2026-06-23/006-session-remaining-sidebar-display.md) |
| 2026-06-23 | 005 | Dockerized Ceph 기반 bind mount 스토리지 설계 재작성 | [상세](devlog/2026-06-23/005-dockerized-ceph-bind-mount-storage.md) |
| 2026-06-23 | 006 | 매크로 스케줄 실행 이력 결과 모달 전환 | [상세](devlog/2026-06-23/006-macro-schedule-history-result-modal.md) |
| 2026-06-23 | 007 | 컨테이너 버전 변경 런타임 이미지 불일치 재적용 보정 | [상세](devlog/2026-06-23/007-service-container-version-runtime-mismatch-apply.md) |
| 2026-06-23 | 008 | Ceph OSD slot backing과 CRUSH host 분산 정책 보강 | [상세](devlog/2026-06-23/008-ceph-osd-slot-crush-host-policy.md) |
| 2026-06-23 | 009 | 매크로 스케줄 결과 모달 stdout/stderr 세로 배치 | [상세](devlog/2026-06-23/009-macro-schedule-result-stream-layout.md) |
| 2026-06-23 | 010 | CephFS Storage Docker Infra 적용 설계 문서 추가 | [상세](devlog/2026-06-23/010-ceph-storage-application-plan.md) |
| 2026-06-23 | 011 | 세션 지속시간 변경 시 현재 세션 만료 시간 갱신 | [상세](devlog/2026-06-23/011-session-ttl-current-session-refresh.md) |
| 2026-06-23 | 012 | 독립 서버 보존과 Swarm OSD 구성 마법사 설계 반영 | [상세](devlog/2026-06-23/012-independent-server-swarm-osd-wizard.md) |
| 2026-06-23 | 013 | 사이드바 세션 남은 시간 카드에 연장 버튼 추가 | [상세](devlog/2026-06-23/013-session-remaining-extend-button.md) |
| 2026-06-23 | 014 | GlusterFS 대안 검토와 CephFS 기본값 유지 근거 보강 | [상세](devlog/2026-06-23/014-glusterfs-alternative-review.md) |
| 2026-06-23 | 015 | GlusterFS 설계 내용 제거와 CephFS 적용 작업 지시서 작성 | [상세](devlog/2026-06-23/015-ceph-storage-reviewops-task-instructions.md) |
| 2026-06-23 | 016 | CephFS Storage 작업 지시서 구현 가능성 검토 | [상세](devlog/2026-06-23/016-ceph-storage-implementation-feasibility-review.md) |
| 2026-06-23 | 017 | CephFS 전환 시 volume artifact 경로 제거 정책 반영 | [상세](devlog/2026-06-23/017-cephfs-remove-volume-artifact-paths.md) |
| 2026-06-23 | 018 | Agent 기반 생성과 서비스 동작의 CephFS Storage 계약 보강 | [상세](devlog/2026-06-23/018-agent-storage-contract.md) |
| 2026-06-24 | 001 | Storage 메뉴와 읽기 전용 개요 페이지 추가 | [상세](devlog/2026-06-24/001-storage-readonly-overview.md) |
| 2026-06-24 | 002 | Ceph Storage DB migration과 Struct skeleton 추가 | [상세](devlog/2026-06-24/002-ceph-storage-model-skeleton.md) |
| 2026-06-24 | 003 | 서버 상세의 독립/Swarm Storage 분기 표시 정리 | [상세](devlog/2026-06-24/003-independent-swarm-server-storage-branch.md) |
| 2026-06-24 | 004 | Ceph preflight와 cluster bootstrap PoC 구현 | [상세](devlog/2026-06-24/004-ceph-preflight-bootstrap-poc.md) |
| 2026-06-24 | 005 | 실제 DB schema 대조 후 Ceph Storage migration 적용 | [상세](devlog/2026-06-24/005-ceph-storage-db-apply.md) |
| 2026-06-24 | 006 | 독립 서버 Storage 탭을 단일 경고 메시지로 단순화 | [상세](devlog/2026-06-24/006-independent-storage-warning-only.md) |
| 2026-06-24 | 007 | Ceph preflight 결과 모달과 보정 안내 추가 | [상세](devlog/2026-06-24/007-ceph-preflight-modal-remediation.md) |
| 2026-06-24 | 008 | Dockerized Ceph runtime과 OSD 슬롯 구성 마법사 연결 | [상세](devlog/2026-06-24/008-dockerized-ceph-osd-wizard.md) |
| 2026-06-24 | 009 | CephFS host mount와 service storage mount 모델 구현 | [상세](devlog/2026-06-24/009-cephfs-host-service-mount-model.md) |
| 2026-06-24 | 010 | 서비스 생성 Wizard 저장소 확인 단계와 bind mount 자동 변환 연결 | [상세](devlog/2026-06-24/010-service-create-storage-step.md) |
| 2026-06-24 | 011 | Ceph preflight 비동기 실행과 중간 과정 polling 보강 | [상세](devlog/2026-06-24/011-ceph-preflight-async-progress.md) |
| 2026-06-24 | 012 | Storage 화면 Swarm 전용화와 OSD 자동 슬롯 계획 UX 개선 | [상세](devlog/2026-06-24/012-storage-swarm-only-osd-auto-plan.md) |
| 2026-06-24 | 013 | Storage 클러스터 서버 카드 통합과 Operation log 탭 위치 조정 | [상세](devlog/2026-06-24/013-storage-cluster-server-compact-layout.md) |
| 2026-06-24 | 014 | Storage bootstrap 카드 서버 목록 압축과 불필요한 설명 제거 | [상세](devlog/2026-06-24/014-storage-bootstrap-compact-summary.md) |
| 2026-06-24 | 015 | Storage bootstrap 서버 행을 이름/IP/OSD 버튼만 표시하도록 압축 | [상세](devlog/2026-06-24/015-storage-bootstrap-server-row-minimal.md) |
| 2026-06-24 | 016 | 매크로 스케줄 이력 일자 그룹화와 결과 탭/페이지네이션 적용 | [상세](devlog/2026-06-24/016-macro-schedule-history-pagination-tabs.md) |
| 2026-06-24 | 017 | Storage bootstrap 서버 목록을 가로 배지 카드로 변경 | [상세](devlog/2026-06-24/017-storage-bootstrap-horizontal-server-badges.md) |
| 2026-06-24 | 018 | 매크로 스케줄 이력과 결과 모달에 실행 시간 표시 | [상세](devlog/2026-06-24/018-macro-schedule-history-time-labels.md) |
| 2026-06-24 | 019 | Ceph 마스터 bootstrap과 managed loop OSD 슬롯 선택 추가 | [상세](devlog/2026-06-24/019-ceph-master-managed-loop-osd.md) |
| 2026-06-24 | 020 | 매크로 스케줄 이력 시간 표시 타임존 정규화 | [상세](devlog/2026-06-24/020-macro-schedule-history-timezone-normalization.md) |
| 2026-06-24 | 021 | Ceph 마스터 구성 카드 표시 조건 보정 | [상세](devlog/2026-06-24/021-ceph-master-bootstrap-visibility.md) |
| 2026-06-24 | 022 | Ceph 마스터 bootstrap 실패 표시와 MON 실행 경로 보정 | [상세](devlog/2026-06-24/022-ceph-master-bootstrap-feedback-runtime.md) |
| 2026-06-24 | 023 | Ceph 마스터 bootstrap preflight 완화와 MGR/MDS 자동 배치 | [상세](devlog/2026-06-24/023-ceph-master-mgr-mds-bootstrap.md) |
| 2026-06-24 | 024 | Ceph legacy image tag 정규화 | [상세](devlog/2026-06-24/024-ceph-legacy-image-normalization.md) |
| 2026-06-24 | 025 | Storage 실행 결과 모달과 local-master SSH 우회 보정 | [상세](devlog/2026-06-24/025-storage-operation-modal-local-master.md) |
| 2026-06-24 | 026 | OSD 슬롯 구성 마법사 다중 슬롯 개수 조정 지원 | [상세](devlog/2026-06-24/026-storage-osd-multi-slot-count.md) |
| 2026-06-24 | 027 | mini-new2 managed loop OSD 3개 생성 오류 보정 | [상세](devlog/2026-06-24/027-mini-new2-managed-loop-osd-validation.md) |
| 2026-06-24 | 028 | Storage 개요를 Ceph 대시보드형 OSD 배치 화면으로 재구성 | [상세](devlog/2026-06-24/028-storage-overview-ceph-dashboard-layout.md) |
| 2026-06-25 | 001 | local-master OSD daemon allowlist와 prepared 슬롯 재시도 보정 | [상세](devlog/2026-06-25/001-local-master-osd-allowlist-retry.md) |
| 2026-06-25 | 002 | Storage cluster/preflight 버튼 제거와 CephFS 서비스 배포 검증 | [상세](devlog/2026-06-25/002-storage-cephfs-service-validation.md) |
