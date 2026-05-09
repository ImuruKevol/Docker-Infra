# Docker Infra 남은 TODO

- 기준일: 2026-05-09
- 전체 TODO: `docs/docker-infra-development-todo.md`
- 서비스 관리 검수 TODO: `docs/service-management-audit-todo.md`
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
- [x] 활성화 시 마스터 노드에 Harbor 설치/자동 실행
- [x] Harbor data directory와 volume 기본값 정의
- [x] 설치 전 필요 포트와 예상 저장 경로 안내
- [x] 설치 실패 시 건너뛰기/비활성화 선택지 제공
- [x] 설치 완료 후 백업 시스템 상태와 남은 용량 표시

## P3. 내장 Harbor 백업 시스템

- [x] Harbor installer/`harbor.yml` 리소스를 프로젝트 내부 모델로 추가
- [x] Harbor 시작/정지/재시작 API 구현
- [x] Harbor 상태 확인 API 구현
- [x] Harbor storage 사용량/남은 용량 계산
- [x] 내부 Harbor 인증 정보 자동 생성과 secret 저장
- [x] 사용자가 Harbor 계정/token을 직접 다루지 않도록 UI 숨김
- [x] 백업 시스템 비활성화 상태에서도 로컬 이미지 화면이 정상 동작하도록 분기
- [x] 백업 시스템 삭제/초기화 위험 모달 구현

## P4. 서비스 이미지 백업과 복원

- [x] 서비스 생성/Compose 갱신 시 이미지, tag, digest 기록
- [x] 자동 백업 정책 저장: 기본 비활성, 실행 주기, 허용 시간대, 회당 처리 개수
- [x] 예약 조건을 만족하는 이미지 이력을 내부 Harbor에 저장하는 실행 API
- [x] docker commit 기반 컨테이너 스냅샷 백업 수동 실행
- [x] 자동 백업 정책에서 스냅샷 포함 여부와 commit pause 여부 설정
- [x] WIZ 앱 활동 기반 예약 실행 tick 연결
- [x] 서비스 이미지 수동 내부 Harbor 백업 실행
- [x] 동일 digest 중복 백업 방지
- [x] 서비스별 이미지 이력 목록 UI 추가
- [x] 이미지 이력 기준 Compose 복원 API 구현
- [x] 복원 전 영향 범위 확인 모달 구현
- [x] 백업 성공/실패를 서비스 상세에 표시
- [x] 서비스별 보존 개수 정책 구현
- [x] 미사용 N일 이상 백업 이미지 삭제 구현
- [x] 현재 서비스에서 사용하지 않는 백업 이미지 일괄 삭제 구현

## P5. 서비스 생성 wizard

- [x] 기본 생성 화면에서 Compose YAML 편집기를 숨긴다.
- [x] 서비스 이름/설명 단계 구현
- [x] 이미지 선택 단계 구현
- [x] 이미지 버전/tag 선택 단계 구현
- [x] 포트 자동 감지 또는 선택 단계 구현
- [x] 도메인 선택/입력 단계 구현
- [x] 등록된 도메인 사용 또는 도메인 미사용만 wizard에서 처리
- [x] 도메인 선택 시 내부 포트와 nginx 연결 미리보기 표시
- [x] 도메인 앞 주소 입력을 도메인 선택 앞에 배치
- [x] 도메인 연결 포트를 버튼형 radio group으로 선택
- [x] 환경변수 폼을 2단계 고급 설정 토글 안에 배치
- [x] 볼륨/데이터 보관 폴더를 2단계 고급 설정 토글 안에 배치
- [x] 실행 서버 직접 선택 UI 제거
- [x] 최종 요약 단계 구현
- [x] 배포 실행 단계 구현
- [x] 고급 모드에서만 Compose 원문 편집 제공
- [x] wizard form 값과 고급 Compose 수정값 충돌 표시
- [x] 서비스 생성 wizard를 모달에서 `/services/create` 독립 화면으로 전환
- [x] 운영자에게 서비스 ID와 내부 service key 입력을 요구하지 않도록 제거
- [x] 템플릿 선택 후 다음 단계에서는 템플릿 변경을 잠금 처리
- [x] 다중 Compose service 기준 이미지와 내부 포트 입력 UI 구현
- [x] 환경변수/볼륨 입력은 고급 설정 토글 안으로 이동
- [x] 이미지 존재 확인: 로컬 이미지 확인 후 Docker Hub 확인
- [x] 도메인은 등록된 도메인 사용 또는 미사용만 제공
- [x] SSL 방식은 업로드 인증서/자동 certbot 기준으로 내부 자동 결정
- [x] 서버 직접 선택 UI 제거
- [x] 저장 전 이미지, 포트, 볼륨, 도메인, nginx 설정 중복 자동 사전 점검
- [x] 배포 전 사용 중인 published port를 확인하고 다음 가용 port로 자동 조정
- [x] 배포 전 published port 조정 결과를 service domain metadata에 반영

## P5-1. 서비스 관리 UX/자동화 검수 후속

- [x] `/services` 목록 초기 렌더에서 첫 서비스 상세 await 제거
- [x] 서비스 상세 요청 race 방지 token 적용
- [x] 목록 API에서 편집/상세 전용 option 로딩 분리
- [x] 서비스 수정 모달을 열 때 도메인 option 지연 로드
- [x] `/services/create` 일반 생성 흐름에서 템플릿 선택 필수화
- [x] 템플릿 없는 기본 `nginx:alpine` fallback 제거
- [x] 생성 API에서 템플릿 또는 Compose import source 필수 검증
- [x] 템플릿 metadata에 공개 endpoint와 사용자용 구성요소 라벨 추가
- [x] 도메인 연결 포트는 공개 endpoint를 우선 자동 선택
- [x] 템플릿 DB/app secret은 생성 시 랜덤 자동 생성
- [x] 생성 2단계 일반 영역에서 이미지명/tag/내부 port 직접 입력 제거
- [x] 이미지명/tag/내부 port 직접 수정은 고급 설정으로 격리
- [x] preflight 이미지/포트 검사를 실제 배포 대상 노드 기준으로 고도화
- [x] port 자동 조정 결과를 compose version metadata에 저장
- [x] 상세 고급 정보 영역을 읽기 전용 기술 정보와 위험한 고급 수정으로 분리
- [x] docker commit 스냅샷 백업의 일시 정지 가능성을 확인 모달에 명시

## P6. 서비스 배포/수정/롤백

- [x] 배포 방식 `docker stack deploy` vs `docker compose up -d` 최종 결정
- [x] 배포 API를 Job 없이 operation 실행 방식으로 구현
- [x] 배포 output streaming 또는 polling 구현
- [x] 배포 성공 후 컨테이너/health/nginx/domain 상태 즉시 갱신
- [x] 공개 port 서비스는 실제 배치 노드의 서버 IP를 확인해 nginx upstream에 자동 반영
- [x] 서비스 수정 wizard 구현
- [x] Compose 버전과 이미지 tag 기준 rollback 구현
- [x] rollback 전 영향 범위 확인 모달 구현
- [x] OpenSSL 자체 인증서 테스트 경로로 생성, 배포, HTTPS, 수정 배포, rollback, 재배포 실동작 확인
- [x] 원격 노드 배치 서비스도 서버 IP 기반 nginx proxy로 HTTPS, 수정 배포, rollback, 재배포 실동작 확인
- [x] 기존 Compose import 흐름을 서비스 wizard와 통합

## P6-1. 서비스 목록/상세 UX 재설계

- [x] 서비스 목록을 운영자용 상태, 접속 주소, 마지막 변경 중심으로 재구성
- [x] namespace, stack name, compose path, digest, 내부 service key를 기본 화면에서 숨김
- [x] 서비스 상세 상단을 접속 주소, 실행 상태, 백업, 최근 처리 요약으로 재구성
- [x] raw Compose, compose version, 파일 브라우저를 고급 정보 영역으로 격리
- [x] 이미지 digest와 operation payload를 기본 화면에서 숨김
- [x] 서비스 수정 기본 모드를 이름, 설명, 이미지 버전, 내부 포트, 도메인, 환경변수/볼륨 폼으로 재구성
- [x] 재배포 문구와 확인 모달을 운영자용 표현으로 정리
- [x] 서버/인증서 상태를 서비스 상세 상단 요약에 더 직접적으로 표시
- [x] 컨테이너 목록은 기본 운영 상태 중심으로 재구성하고 raw 컨테이너 정보는 고급 영역으로 격리
- [x] 문제 상태는 raw error 대신 원인 요약과 권장 조치 버튼으로 표시

## P7. nginx, 도메인, SSL

- [x] 서비스 도메인 기준 nginx server block 자동 생성
- [x] nginx config 원문 편집을 고급 모드로 격리
- [x] 서비스 생성 wizard에서 등록 도메인과 내부 port로 `service_domains` 저장
- [x] 서비스 수정 wizard에서 등록 도메인과 내부 port로 `service_domains` 갱신
- [x] nginx 설정 파일을 직접 쓰지 않아도 서비스와 도메인을 연결할 수 있는 폼 제공
- [x] nginx reload 실패 시 이전 설정 복원
- [x] 도메인 업로드 인증서를 서비스 생성 시 자동 연결 대상으로 선택
- [x] 인증서가 없는 도메인은 배포 과정에서 certbot 무료 인증서 자동 발급
- [x] certbot 실행 output을 operation log로 저장
- [x] 인증서 chain/fullchain 업로드 지원 여부 결정
- [x] 인증서 private key 파일 권한 검증
- [x] 도메인 화면에서 인증서가 적용된 서비스를 표시

## P8. 서버 관리

- [ ] 서버 추가 모달을 서버 이름, IP/host, SSH 계정, 최초 비밀번호 중심으로 단순화
- [ ] 서버 등록 직후 SSH key 생성/설치/fingerprint 저장 흐름 확정
- [ ] Swarm join 자동 실행 결과 요약 표시
- [ ] Docker 미설치 서버 처리 정책 결정
- [ ] 컨테이너 액션 결과를 operation log로 저장
- [ ] reporter token UI 일반 화면 노출 제거
- [ ] 웹 터미널 reconnect, resize, shell 감지, ANSI color 검증

## P9. 이미지 관리

- [x] 외부 Harbor 프로젝트/저장소 관리 UI 제거 또는 내장 백업 시스템 전용으로 축소
- [ ] 로컬 이미지 사용/미사용 필터 유지 검증
- [ ] 이미지 삭제 전 영향 서비스 표시
- [ ] 백업 이미지 목록을 서비스 기준으로 묶어서 표시
- [x] 백업 시스템 비활성화 시 로컬 이미지만 표시
- [ ] 미사용 이미지 일괄 삭제 결과를 operation log로 저장

## P10. 시스템 설정

- [x] Harbor 외부 연동 설정 UI 제거
- [x] 서비스 백업 시스템 설정 섹션 추가
- [x] 백업 시스템 시작/정지/재시작 버튼 추가
- [x] 백업 storage 위치와 사용량 표시
- [x] 서비스 이미지 자동 백업 정책 설정 추가
- [x] 서비스 이미지 수동 백업 실행 버튼 추가
- [x] 미사용 이미지 정리 정책 설정 추가
- [x] 서비스가 사용하지 않는 이미지 정리 실행 버튼 추가
- [ ] 위험 작업 audit log 확인 영역 추가

## P11. 템플릿

- [x] 기본 템플릿을 실제 도메인 연결 가능한 다중 서비스 스택으로 재구성
- [x] 템플릿을 Compose 원문보다 입력값 schema 중심으로 재정의
- [x] 템플릿 선택 시 wizard form으로 자동 매핑
- [x] WordPress, Nextcloud, Odoo, Wiki.js처럼 웹+DB/캐시가 함께 동작하는 쉬운 분류로 정리
- [ ] 템플릿 편집/릴리즈 UI는 고급 관리 기능으로 분리
- [x] 기본 템플릿에서 서비스 ID/container name 같은 불필요한 운영자 입력 제거 방향 반영

## P12. 매크로와 터미널

- [ ] 매크로 실행 이력을 Job이 아닌 operation log로 전환
- [ ] 매크로 streaming 출력 안정화
- [ ] 매크로 위험도 표시
- [ ] 서버 전용/전역 매크로 선택 UI 최종 정리
- [ ] 웹 터미널 실사용 시나리오 Playwright 또는 수동 검증 절차 작성

## P13. DB와 API 계약

- [x] `operation_logs` 또는 `audit_logs` schema 설계
- [x] `service_image_backups` schema 설계
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
- [x] API 테스트에서 외부 Harbor fixture 제거
- [x] cleanup 순서에서 Job 관련 단계 제거
- [ ] 빌드와 정적 문서 링크 검증 추가
