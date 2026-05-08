# Docker Infra 남은 TODO

- 기준일: 2026-05-08
- 전체 TODO: `docs/docker-infra-development-todo.md`
- 목적: 실제 남은 작업만 빠르게 확인하기 위한 실행 체크리스트

## P0. 방향 전환 정리

- [x] `docs/docker-infra-design.md`에서 Job Queue/Worker 설계를 제거한다.
- [x] `docs/docker-infra-design.md`에서 외부 Harbor 연동 설명을 제거한다.
- [x] 내장 Harbor 백업 시스템 설계를 추가한다.
- [x] 서비스 생성 wizard 중심 설계를 추가한다.
- [x] runtime 문서에서 Job API와 외부 Harbor API를 제거한다.
- [x] OpenAPI 문서에서 Job API와 외부 Harbor API를 제거한다.
- [x] README에 제품 패키징 전제, nginx 고정, 내장 백업 시스템 선택 흐름을 반영한다.

## P1. Job 시스템 제거

- [x] `/api/jobs`, `/api/jobs/<path:path>` route 제거 또는 deprecated 처리
- [x] `struct/jobs*` 모델 제거 또는 deprecated 처리
- [x] DB migration으로 `jobs`, `job_steps`, `job_logs` 제거 또는 deprecated 처리
- [x] 서비스 상세의 최근 작업 UI를 operation history로 교체
- [x] 서버/서비스 위험 작업 결과를 lightweight operation log로 통일
- [x] 이미지/도메인 위험 작업 결과를 lightweight operation log로 통일
- [x] 테스트 cleanup에서 Job cancel/wait 단계 제거

## P2. 최초 구성 마법사

- [x] 최초 구성 화면에 `서비스 백업 시스템 구성` 토글 추가
- [x] 백업 시스템 토글 기본값 비활성화
- [ ] 활성화 시 마스터 노드에 Harbor Compose 자동 실행
- [x] Harbor data directory와 volume 기본값 정의
- [x] 설치 전 필요 포트와 예상 저장 경로 안내
- [ ] 설치 실패 시 재시도/건너뛰기/비활성화 선택지 제공
- [x] 설치 완료 후 백업 시스템 상태와 남은 용량 표시

## P3. 내장 Harbor 백업 시스템

- [ ] Harbor Compose 템플릿을 프로젝트 내부 리소스로 추가
- [ ] Harbor 시작/정지/재시작 API 구현
- [ ] Harbor 상태 확인 API 구현
- [ ] Harbor storage 사용량/남은 용량 계산
- [ ] 내부 Harbor 인증 정보 자동 생성과 secret 저장
- [ ] 사용자가 Harbor 계정/token을 직접 다루지 않도록 UI 숨김
- [ ] 백업 시스템 비활성화 상태에서도 서비스 배포가 정상 동작하도록 분기
- [ ] 백업 시스템 삭제/초기화 위험 모달 구현

## P4. 서비스 이미지 백업과 복원

- [ ] 서비스 배포 시 이미지, tag, digest 기록
- [ ] 백업 시스템 활성화 시 서비스 이미지 내부 Harbor 저장
- [ ] 동일 digest 중복 백업 방지
- [ ] 서비스별 백업 버전 목록 UI 추가
- [ ] 백업 버전 기준 복원 API 구현
- [ ] 복원 전 영향 범위 확인 모달 구현
- [ ] 서비스별 보존 개수 정책 구현
- [ ] 미사용 N일 이상 백업 이미지 삭제 구현
- [ ] 현재 서비스에서 사용하지 않는 백업 이미지 일괄 삭제 구현

## P5. 서비스 생성 wizard

- [ ] 기본 생성 화면에서 Compose YAML 편집기를 숨긴다.
- [ ] 서비스 이름/설명 단계 구현
- [ ] 이미지 선택 단계 구현
- [ ] 이미지 버전/tag 선택 단계 구현
- [ ] 포트 자동 감지 또는 선택 단계 구현
- [ ] 도메인 선택/입력 단계 구현
- [ ] 등록된 도메인 선택 또는 신규 도메인 연결을 wizard 안에서 처리
- [ ] 도메인 선택 시 내부 포트와 nginx 연결 미리보기 표시
- [ ] 환경변수 폼 단계 구현
- [ ] 볼륨/데이터 보관 폴더 단계 구현
- [ ] 실행 서버 또는 자동 배치 선택 단계 구현
- [ ] 최종 요약과 배포 실행 단계 구현
- [ ] 고급 모드에서만 Compose 원문 편집 제공
- [ ] wizard form 값과 고급 Compose 수정값 충돌 표시

## P6. 서비스 배포/수정/롤백

- [ ] 배포 방식 `docker stack deploy` vs `docker compose up -d` 최종 결정
- [ ] 배포 API를 Job 없이 operation 실행 방식으로 구현
- [ ] 배포 output streaming 또는 polling 구현
- [ ] 배포 성공 후 컨테이너/health/nginx/domain 상태 즉시 갱신
- [ ] 서비스 수정 wizard 구현
- [ ] Compose 버전과 이미지 tag 기준 rollback 구현
- [ ] rollback 전 영향 범위 확인 모달 구현
- [ ] 기존 Compose import 흐름을 서비스 wizard와 통합

## P7. nginx, 도메인, SSL

- [ ] 서비스 도메인 기준 nginx server block 자동 생성
- [ ] nginx config 원문 편집을 고급 모드로 격리
- [ ] 서비스 생성/수정 wizard에서 domain, 내부 port, SSL 방식으로 `service_domains` 저장
- [ ] nginx 설정 파일을 직접 쓰지 않아도 서비스와 도메인을 연결할 수 있는 폼 제공
- [ ] nginx reload 실패 시 이전 설정 복원
- [ ] 도메인 업로드 인증서를 서비스에 자동 연결
- [ ] 서비스 화면에서 certbot 무료 인증서 발급 구현
- [ ] certbot 실행 output을 operation log로 저장
- [ ] 인증서 chain/fullchain 업로드 지원 여부 결정
- [ ] 인증서 private key 파일 권한 검증
- [ ] 도메인 화면에서 인증서가 적용된 서비스를 표시

## P8. 서버 관리

- [ ] 서버 추가 모달을 서버 이름, IP/host, SSH 계정, 최초 비밀번호 중심으로 단순화
- [ ] 서버 등록 직후 SSH key 생성/설치/fingerprint 저장 흐름 확정
- [ ] Swarm join 자동 실행 결과 요약 표시
- [ ] Docker 미설치 서버 처리 정책 결정
- [ ] 컨테이너 액션 결과를 operation log로 저장
- [ ] reporter token UI 일반 화면 노출 제거
- [ ] 웹 터미널 reconnect, resize, shell 감지, ANSI color 검증

## P9. 이미지 관리

- [ ] 외부 Harbor 프로젝트/저장소 관리 UI 제거 또는 내장 백업 시스템 전용으로 축소
- [ ] 로컬 이미지 사용/미사용 필터 유지 검증
- [ ] 이미지 삭제 전 영향 서비스 표시
- [ ] 백업 이미지 목록을 서비스 기준으로 묶어서 표시
- [ ] 백업 시스템 비활성화 시 로컬 이미지만 표시
- [ ] 미사용 이미지 일괄 삭제 결과를 operation log로 저장

## P10. 시스템 설정

- [ ] Harbor 외부 연동 설정 UI 제거
- [ ] 서비스 백업 시스템 설정 섹션 추가
- [ ] 백업 시스템 시작/정지/재시작 버튼 추가
- [ ] 백업 storage 위치와 사용량 표시
- [ ] 미사용 이미지 정리 정책 설정 추가
- [ ] 서비스가 사용하지 않는 이미지 정리 실행 버튼 추가
- [ ] 위험 작업 audit log 확인 영역 추가

## P11. 템플릿

- [ ] 템플릿을 Compose 원문보다 입력값 schema 중심으로 재정의
- [ ] 템플릿 선택 시 wizard form으로 자동 매핑
- [ ] DB, WAS, static app, reverse app 등 쉬운 분류 정리
- [ ] 템플릿 편집/릴리즈 UI는 고급 관리 기능으로 분리
- [ ] 기본 템플릿에서 불필요하게 운영자가 직접 만질 값 제거

## P12. 매크로와 터미널

- [ ] 매크로 실행 이력을 Job이 아닌 operation log로 전환
- [ ] 매크로 streaming 출력 안정화
- [ ] 매크로 위험도 표시
- [ ] 서버 전용/전역 매크로 선택 UI 최종 정리
- [ ] 웹 터미널 실사용 시나리오 Playwright 또는 수동 검증 절차 작성

## P13. DB와 API 계약

- [x] `operation_logs` 또는 `audit_logs` schema 설계
- [ ] `service_image_backups` schema 설계
- [x] backup system config schema 설계
- [ ] proxy config schema를 nginx 전용으로 정리
- [ ] certificates schema를 도메인 기준으로 정리
- [x] OpenAPI에서 Job API 제거
- [ ] OpenAPI에 백업 시스템 API 추가
- [ ] OpenAPI에 서비스 wizard API 추가
- [ ] OpenAPI에 operation log API 추가

## P14. 테스트

- [ ] Playwright 최초 구성 wizard 테스트 갱신
- [ ] Playwright 서비스 생성 wizard 테스트 추가
- [ ] Playwright 도메인 인증서 업로드 테스트 추가
- [ ] Playwright 백업 시스템 활성화/비활성화 테스트 추가
- [x] API 테스트에서 Job fixture 제거
- [ ] API 테스트에서 외부 Harbor fixture 제거
- [x] cleanup 순서에서 Job 관련 단계 제거
- [ ] 빌드와 정적 문서 링크 검증 추가
