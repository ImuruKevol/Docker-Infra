# Docker Infra 전체 TODO

- 문서 상태: 전체 백로그 재정의
- 기준일: 2026-05-08
- 남은 작업 체크리스트: `docs/docker-infra-remaining-todo.md`
- 서비스 관리 검수 TODO: `docs/service-management-audit-todo.md`
- 기준 방향: 미니 PC/데스크탑에 패키징해 판매하는 단일 운영 장비형 Docker Infra

## 0. 새 전제

Docker Infra는 개발자가 아니라 전산 담당자 또는 일반 관리자가 쓰는 서비스다. 사용자는 IP, port, domain 정도만 알아도 서버 등록, 서비스 배포, 도메인 연결, 인증서 적용, 이미지 백업을 진행할 수 있어야 한다.

이번 구조 단순화로 다음 전제를 고정한다.

- 웹서버는 Ubuntu 24.04 기본 nginx로 고정한다.
- Apache2/httpd 선택, 경로 편집, daemon 이름 편집은 제공하지 않는다.
- GitLab 연동과 Docker build/push 플로우는 제공하지 않는다.
- 외부 Harbor 연동은 사용자 흐름에서 제거한다.
- Harbor는 Docker Infra가 등록된 서버 중 마스터 노드에 직접 띄우는 서비스 이미지 백업/버전 관리 시스템으로만 사용한다.
- 서비스 배포는 이미 존재하는 이미지를 선택해 Docker Compose로 실행하는 흐름이다.
- Job Queue, Job Step, Job Worker 같은 별도 Job 시스템은 제거한다.
- 긴 작업은 API가 직접 실행하고, 필요한 경우 lightweight operation log 또는 streaming response로 결과를 보여준다.
- Compose YAML, nginx config 원문 편집기는 기본 화면에 노출하지 않고 고급 모드에서만 제공한다.
- 서비스와 도메인 연결은 nginx 원문 수정이 아니라 서비스 생성/수정 마법사의 폼으로 처리한다.
- 사용자의 입력은 이름, 이미지, 버전, 포트, 도메인, 환경변수, 볼륨, 서버 선택 같은 폼으로 받는다.

## 1. 상태 기준

| 상태 | 의미 |
|---|---|
| Done | 현재 구현되어 있고 새 방향과 충돌하지 않음 |
| Rework | 구현은 있으나 새 방향에 맞게 재설계 필요 |
| Todo | 아직 구현 필요 |
| Remove | 제거 또는 비활성화 필요 |

## 2. 제품 흐름 목표

### 2.1 최초 구성

상태: Rework

사용자는 처음 접속하면 다음만 결정한다.

1. 관리자 비밀번호
2. 서비스 백업 시스템 구성 여부

서비스 백업 시스템은 기본 비활성화다. 활성화하면 마스터 노드에서 Harbor installer를 통해 로컬 Harbor를 자동 실행하고, 백업 저장소 용량과 상태를 Docker Infra가 관리한다.

필요한 TODO:

- [Done] 최초 구성 마법사에 `서비스 백업 시스템 구성` 토글 추가
- [Done] 토글 기본값 비활성화
- [Done] 활성화 시 마스터 노드에 Harbor 설치/실행
- [Done] Harbor data directory를 WIZ root `data/backup-harbor/` 또는 운영 전용 volume으로 고정
- [Done] 설치 전 예상 사용 포트, 저장 경로, 필요 용량 안내
- [Done] 설치 후 백업 시스템 상태와 남은 용량 표시
- [Done] 실패 시 건너뛰기/비활성화 선택지와 재시도 경로 제공

### 2.2 기본 운영 화면

상태: Rework

운영자는 대시보드에서 다음을 바로 확인한다.

- 서버 정상 여부
- 서비스 정상 여부
- 도메인/인증서 문제
- 백업 시스템 사용 여부와 남은 용량
- 정리할 수 있는 미사용 이미지 수

필요한 TODO:

- dashboard summary에서 Job/Worker 상태 제거
- backup system 상태 카드 추가
- 문제 해결 버튼을 각 화면으로 연결
- 기술적인 raw output 대신 요약 상태와 권장 동작 표시

## 3. Job 시스템 제거

상태: Rework

기존 Job 시스템은 GitLab clone, Docker build, Harbor push, 다단계 배포를 추적하기 위해 필요했다. 현재 방향에서는 이미 존재하는 이미지를 단순 배포하고, Harbor도 내장 백업 저장소이므로 별도 Job Queue가 과하다.

제거 대상:

- `jobs`, `job_steps`, `job_logs` 중심 API
- `/api/jobs`, `/api/jobs/<path:path>` route
- Job 모델과 lifecycle/logs struct
- 화면의 최근 Job, Job 로그, Job 상태 의존 UI
- OpenAPI와 문서의 Job Queue/Worker 설명
- 테스트의 Job fixture와 cleanup 규칙

대체 구조:

- 즉시 실행 API: 서비스 배포, 컨테이너 제어, 백업/정리 작업을 직접 실행
- operation log: 단일 operation_id, type, status, started_at, finished_at, message, result 정도만 저장
- streaming output: 매크로 실행, 터미널, certbot, 배포 로그처럼 화면에서 필요한 경우에만 WebSocket/SSE로 표시
- audit log: 위험 작업의 요청자, 대상, 결과, 오류만 저장

Done:

- DB migration으로 Job table 제거 또는 deprecated 처리
- 코드에서 `wiz.model("struct").jobs` 의존 제거
- 서비스 상세의 최근 작업 영역을 operation history로 교체
- 서버/서비스 위험 작업의 결과 기록을 operation log로 통일
- 이미지/도메인 위험 작업의 결과 기록을 operation log로 통일
- cleanup 문서와 테스트에서 Job cancel/wait 단계 제거

## 4. 서버 관리

상태: Rework

현재 목표는 서버를 추가하면 연결 확인, SSH key 준비, Docker/Swarm join, 상태 수집까지 가능한 한 자동으로 이어지는 것이다.

Done:

- 마스터 노드 자동 등록 방향
- 서버 상세 CPU/memory/storage 자동 갱신
- 컨테이너 상태/포트 표시 개선
- 컨테이너 run/restart/stop 액션
- 웹 터미널 탭
- 전역/서버 전용 매크로 실행

필요한 TODO:

- 서버 추가 모달을 더 단순화: 서버 이름, IP/host, SSH 계정, 최초 비밀번호만 입력
- 등록 직후 SSH key 생성/설치/fingerprint 저장을 하나의 흐름으로 처리
- Swarm join 자동 실행과 결과 요약 표시
- Docker 미설치 서버일 때 설치 안내 또는 Docker 설치 자동화 옵션 제공
- 컨테이너 액션 결과를 Job이 아니라 operation log로 저장
- 미등록 컨테이너의 Compose 등록 흐름을 서비스 생성 wizard와 통합
- 웹 터미널 실제 shell 환경, ANSI color, resize, reconnect 안정화
- reporter token 발급 UI는 일반 사용자 화면에서 숨기고 내부 설정으로 격리

## 5. 서비스 생성 및 관리

상태: Rework

서비스 관리의 기본 화면은 YAML 편집기가 아니라 wizard여야 한다. 사용자는 이미지와 간단한 설정만 선택하고, Docker Infra가 Compose와 nginx 설정을 생성한다.

### 5.1 서비스 생성 wizard

Done:

- 새 서비스 버튼은 `/services/create` 독립 화면으로 진입
- 운영자가 서비스 ID, namespace, 내부 service key, container name을 직접 입력하지 않음
- 서비스 namespace와 내부 service key는 중복 확인 후 자동 생성
- 단계 1: 서비스 이름, 설명, 템플릿 선택
- 템플릿은 1단계 이후 잠금 처리
- 단계 2: Compose에 포함된 여러 service의 이미지 이름, 버전/tag, 내부 포트 입력
- 단계 2 안에 고급 설정 토글을 두고 환경변수와 데이터 보관 설정을 숨김 처리
- 이미지 존재 확인: 로컬 이미지 저장소 확인 후 Docker Hub 확인
- 단계 3: 등록된 도메인 사용 또는 도메인 미사용 선택
- 도메인 앞 주소 입력은 도메인 선택보다 먼저 배치
- 도메인 연결 port는 select가 아니라 버튼형 radio group으로 선택
- 신규 도메인 연결, 공개 도메인 직접 입력, SSL 방식 수동 선택은 생성 wizard에서 제거
- 등록 도메인에 업로드 인증서가 있으면 자동 사용, 없으면 certbot 자동 발급 대상으로 처리
- 단계 4: 최종 요약 후 서비스 초안 저장 또는 저장 후 배포
- 단계 4 진입 및 저장 직전에 이미지, 포트, 볼륨, 도메인, nginx 설정 중복을 자동 사전 점검
- 서버 직접 선택 UI 제거, 기본 배치는 자동 처리
- 배포 직전 published port 사용 여부를 확인하고 충돌 시 다음 가용 port로 자동 조정
- 저장 전 preflight에서 등록된 실행 서버 후보의 이미지 inspect/pull 가능성과 포트 사용 여부를 확인
- 배포 직전 published port 조정 결과를 service domain metadata와 compose version metadata에 반영
- Compose YAML은 고급 모드에서만 표시
- 고급 Compose 원문과 wizard form 값 충돌 표시

필요한 TODO:

- `docs/service-management-audit-todo.md`의 P0/P1 항목을 서비스 생성 기준 TODO의 최종 기준으로 삼는다.
- 템플릿 선택이 없는 기본 nginx fallback 제거
- 템플릿 공개 endpoint 기준으로 도메인 연결 port 자동 선택
- 템플릿 secret 값은 서비스 생성 시 자동 생성
- 일반 화면에서 이미지명/tag/내부 port 직접 입력을 고급 설정으로 격리
- 템플릿 schema와 wizard form 자동 매핑 고도화
- [Done] port 자동 조정 결과를 compose version metadata에 표시

### 5.2 템플릿 기반 생성

완료된 작업:

- 기본 템플릿을 실제 도메인 연결이 가능한 다중 서비스 스택으로 교체
- 기본 템플릿은 WordPress, Nextcloud, Odoo, Wiki.js 4종으로 정리
- 각 템플릿은 web/WAS 역할과 DB 또는 cache 같은 내부 구성요소를 함께 포함
- DB, Redis 같은 내부 구성은 외부 공개 port 없이 Compose 내부 네트워크로만 연결
- 템플릿은 Compose 원문보다 `필요 입력값 schema` 중심으로 관리
- 템플릿 선택 시 이름, 이미지, 포트, 환경변수, volume 필드를 wizard form으로 자동 매핑
- 서비스 ID, container name 같은 운영자에게 불필요한 입력은 기본 템플릿 흐름에서 제거
- 기존 단일 컨테이너 seed와 Harbor/GitLab 계열 seed는 기본 제공 템플릿에서 제거

필요한 TODO:

- 템플릿 schema의 field type, secret 처리, 조건부 표시 규칙을 더 세분화
- 템플릿 편집 화면은 관리자 고급 기능으로 유지
- 템플릿 릴리즈와 버전 이력은 유지하되 서비스 생성 기본 흐름에서는 숨김

### 5.3 배포/수정/롤백

필요한 TODO:

- `docker compose config` 또는 내부 validator로 검증
- 배포 방식은 `docker stack deploy` 기준
- [Done] 배포 로그는 Job이 아니라 operation output으로 저장하고 서비스 상세에서 polling으로 확인
- [Done] 배포 성공 후 서비스 상태, 컨테이너 상태, health check 결과를 즉시 갱신
- [Done] 공개 port가 있는 서비스는 실제 배치 노드의 서버 IP를 확인해 nginx upstream에 자동 반영
- [Done] 서비스 수정은 wizard form으로 제공
- Compose 원문 수정은 고급 모드
- [Done] rollback은 Compose 버전과 이미지 tag를 기준으로 단순화
- [Done] rollback 실행 전 영향 범위 확인 모달 제공
- [Done] 기존 서버 Compose 가져오기는 즉시 저장하지 않고 서비스 생성 wizard로 연결

### 5.4 nginx/도메인/SSL 연결

필요한 TODO:

- nginx 설정은 서비스 도메인, 내부 포트, 인증서 상태를 기준으로 자동 생성
- [Done] nginx config 원문 편집기는 고급 모드에서만 제공
- 서비스 생성 wizard에서는 등록된 도메인 선택 또는 도메인 미사용만 제공한다
- 새 도메인 등록은 도메인 관리 화면에서만 처리한다
- 선택한 도메인과 내부 port로 `service_domains` row를 저장한다
- 배포 성공 후 `service_domains`를 기준으로 nginx server block을 생성하고 reload한다
- `nginx -t` 또는 reload 실패 시 이전 설정 파일과 enabled link를 복구한다
- [Done] 서비스 수정 wizard에서도 동일한 도메인 연결 폼을 제공한다
- form에는 `이 도메인으로 접속하면 이 서비스의 이 포트로 연결됨` helper 문구를 표시한다
- 도메인에 업로드 인증서가 있으면 자동 연결
- 인증서가 없으면 배포 과정에서 certbot 무료 인증서 발급을 자동 진행
- [Done] 배포/롤백 테스트 환경에서는 certbot 대신 OpenSSL 자체 인증서를 발급해 nginx SSL 적용 흐름 검증
- certbot 결과와 갱신 상태는 operation log로 저장
- nginx reload 실패 시 이전 설정 복원

### 5.5 서비스 목록과 상세 화면 UX

상태: Rework

현재 서비스 목록과 상세 화면은 namespace, compose path, raw Compose, image digest, operation output 같은 개발자 중심 정보가 앞에 나와 있다. 기본 화면은 이 Docker Infra를 처음 쓰는 전산 담당자도 서비스 상태와 필요한 조치를 바로 이해할 수 있어야 한다.

필요한 TODO:

- [Done] 서비스 목록은 `운영 중`, `준비 중`, `문제 있음` 같은 운영자용 상태 중심으로 재구성
- [Done] 목록에는 서비스 이름, 설명, 접속 주소, 상태, 마지막 변경 시각만 표시
- [Done] namespace, stack name, compose path, digest, 내부 service key는 기본 화면에서 숨김
- [Done] 서비스 상세 상단은 접속 주소, 실행 상태, 백업 상태, 최근 처리 결과를 한눈에 보여주는 운영 요약으로 재구성
- [Done] raw Compose, Compose 버전, 파일 브라우저는 접을 수 있는 고급 정보 영역으로 격리
- [Done] nginx 원문 수정은 별도 확인 모달 뒤에 열리는 고급 수정 흐름으로 분리
- [Done] 컨테이너 raw ID는 접힌 내부 정보로 축소
- [Done] 이미지 digest와 operation payload는 기본 화면에서 숨김
- [Done] 연결 서버와 인증서 상태를 서비스 상세 상단 요약에 더 직접적으로 표시
- [Done] 컨테이너 목록은 기본 운영 상태 중심으로 재구성하고 raw 컨테이너 정보는 고급 영역으로 격리
- [Done] 서비스 수정은 기본 모드에서 이름, 설명, 이미지 버전, 내부 포트, 도메인, 환경변수/볼륨만 폼으로 제공
- [Done] 재배포는 `서비스 적용`, `다시 적용` 같은 운영자용 문구를 사용
- [Done] 백업/스냅샷/복원 버튼 주변에 서비스 영향과 일시 정지 가능성을 사용자용 문구로 표시
- 영향 범위와 자동 port 조정 결과를 확인 모달로 표시
- [Done] 서비스 상세의 문제 상태는 raw error 대신 원인 요약과 권장 조치 버튼으로 표시

## 6. 내장 Harbor 백업 시스템

상태: Rework

Harbor는 외부 연동 대상이 아니라 Docker Infra가 마스터 노드에 띄우는 서비스 이미지 백업/버전 관리 시스템이다.

### 6.1 설치와 상태

필요한 TODO:

- [Done] Harbor installer/`harbor.yml` 생성 리소스를 Docker Infra 내부 모델로 포함
- [Done] 최초 구성 마법사에서 활성화 시 Harbor 설치/실행
- [Done] 시스템 설정에서 백업 시스템 시작/정지/재시작 제공
- [Done] Harbor 관리자 계정과 내부 secret을 자동 생성하고 사용자가 직접 다루지 않게 숨김
- [Done] Harbor URL은 로컬 백업 시스템 URL로 내부 고정
- [Done] Harbor data directory 용량, 사용량, 남은 용량 계산
- [Done] 백업 시스템 disabled 상태에서도 로컬 이미지 중심 화면이 동작
- [Done] 백업 시스템 삭제/초기화 위험 모달 구현

### 6.2 서비스 이미지 백업

필요한 TODO:

- [Done] 서비스 생성/Compose 갱신 시 사용 이미지와 digest를 기록
- [Done] 자동 백업 정책 저장: 기본 비활성화, 실행 주기, 허용 시간대, 회당 처리 개수
- [Done] 예약 조건을 만족하는 이미지 이력만 내부 Harbor에 저장하는 실행 모델/API
- [Done] docker commit 기반 컨테이너 스냅샷 백업을 명시적 선택 옵션으로 제공
- [Done] 자동 백업 정책에서 컨테이너 스냅샷 포함 여부와 commit pause 여부 설정
- [Done] 서비스 상세에서 개별 이미지 이력 기준 수동 스냅샷 백업 실행
- [Done] 서비스 이미지 tag를 내부 Harbor에 수동 백업
- [Done] 백업 tag 규칙 정의: `{service_namespace}/{image_name}:{version_or_timestamp}`
- [Done] 동일 digest 중복 백업 방지
- [Done] 백업 성공/실패를 서비스 상세에 표시
- [Done] 특정 서비스의 이미지 이력 목록과 복원 버튼 제공
- [Done] 복원 시 Compose 이미지 tag를 이력의 image ref로 바꾸고 새 Compose 버전 생성
- [Done] WIZ 앱 활동 기반 예약 실행 tick 연결

### 6.3 백업 저장소 정리

필요한 TODO:

- [Done] 시스템 설정에 미사용 N일 이상 이미지 일괄 삭제 기능
- [Done] 현재 서비스에서 사용하지 않는 이미지 일괄 삭제 기능
- [Done] 서비스별 보존 개수 정책
- 백업 시스템 정지 기능
- 백업 시스템 데이터 삭제는 별도 위험 모달과 문구 필요
- 삭제 전 예상 확보 용량 표시
- 삭제 후 남은 용량 재계산

## 7. 이미지 관리

상태: Rework

이미지 관리는 로컬 이미지와 서비스 백업 이미지를 다루는 화면으로 재정의한다.

필요한 TODO:

- [Done] 외부 Harbor 프로젝트/저장소 관리 UI를 내장 백업 시스템 전용으로 축소
- 서버별 로컬 이미지 목록 유지
- 사용 중/미사용 이미지 필터 유지
- 이미지 용량, 생성일, 마지막 사용일 정렬 유지
- 로컬 이미지 일괄 삭제 유지
- 백업 시스템 이미지 목록은 서비스 기준으로 묶어서 표시
- 이미지 삭제 전 어떤 서비스가 영향을 받는지 표시
- [Done] backup Harbor가 비활성화된 경우 이미지 화면은 로컬 이미지만 보여줌

## 8. 도메인과 SSL

상태: Rework

도메인 관리 화면은 Cloudflare DNS와 업로드 인증서 상태를 담당한다. 서비스 화면은 특정 서비스에 도메인과 인증서를 적용하는 흐름을 담당한다.

Done:

- 도메인별 Cloudflare Zone ID/token 관리
- DNS record 동기화와 CRUD
- DNS record 필터
- 도메인별 인증서 업로드와 만료일 분석

필요한 TODO:

- [Done] 인증서 파일 permission과 private key 보호 정책 강화
- [Done] chain/fullchain 업로드 지원 여부 결정
- [Done] 인증서가 어떤 서비스에 적용 중인지 표시
- 서비스 화면 certbot 발급과 도메인 화면 인증서 목록 연동
- Cloudflare token이 없어도 수동 도메인 관리 가능하게 유지
- A record helper와 Docker Infra master IP 자동 제안

## 9. 시스템 설정

상태: Rework

시스템 설정은 브랜드/접속/백업 시스템/정리 정책 중심으로 유지한다. nginx 경로와 SSL 업로드는 시스템 설정에서 다루지 않는다.

Done:

- Browser title, favicon, logo 저장
- nginx/SSL 설정 섹션 제거

필요한 TODO:

- [Done] Harbor 외부 연동 설정 제거
- [Done] 서비스 백업 시스템 설정 섹션 추가
- [Done] 백업 시스템 활성화/비활성화
- [Done] 백업 시스템 시작/정지/재시작
- [Done] 백업 storage 위치와 사용량 표시
- 미사용 이미지 정리 정책 설정
- 서비스가 사용하지 않는 이미지 정리 실행
- 위험 작업 audit log 확인

## 10. 매크로와 터미널

상태: Rework

Done:

- 전역 매크로 메뉴
- 서버 전용 매크로
- Monaco editor
- 저장 단축키
- 서버 상세 매크로 탭
- 웹 터미널 탭

필요한 TODO:

- 매크로 실행 결과 streaming 안정화
- 매크로 실행 이력은 Job이 아니라 operation log로 전환
- 매크로 권한/위험도 표시
- 서버 전용 매크로와 전역 매크로 UI 정리
- 터미널 reconnect, resize, shell 감지, 색상 처리 검증

## 11. 데이터베이스와 마이그레이션

상태: Rework

필요한 TODO:

- Job table 제거 또는 deprecated migration
- [Done] 외부 Harbor integration table 제거 또는 backup system config로 대체
- [Done] backup_system_settings 테이블 설계
- [Done] service_image_backups 런타임 스키마 추가
- [Done] operation_logs 테이블 추가
- proxy_configs는 nginx 전용으로 단순화
- certificates는 도메인 기준으로 정리
- 기존 데이터 migration 전략 작성

## 12. API 계약과 테스트

상태: Rework

필요한 TODO:

- 백업 시스템 API 추가
- 서비스 wizard API 추가
- operation log API 추가
- 도메인 인증서 API 보강
- Playwright 시나리오를 관리자용 흐름 기준으로 재작성
- [Done] API 테스트는 외부 Harbor fixture 대신 내장 백업 시스템 상태 기준으로 분기
- API 테스트는 WIZ runtime HTTP 호출 기준 유지
- cleanup 순서에서 Job cancel/wait 제거
- build/test command 문서 최신화

Done:

- OpenAPI에서 Job API 제거

## 13. 문서 정리

상태: Rework

Done:

- `docs/docker-infra-design.md`에서 Job Queue/Worker 설계 제거
- 외부 Harbor 연동 설명 제거
- 내장 Harbor 백업 시스템 설계 추가
- 서비스 생성 wizard 상세 설계 추가
- 관리자용 UI/UX 원칙을 설계 문서 전반에 반영
- runtime 문서의 API와 설정 항목 정리
- README에 제품 패키징 전제와 기본 운영 흐름 반영

남은 TODO:

- 테스트 문서와 cleanup 절차에서 Job cancel/wait 제거

## 14. 완료 정의

MVP 완료 기준:

- 최초 구성에서 관리자 비밀번호만으로 기본 운영 진입 가능
- 선택 시 마스터 노드에 백업 시스템을 구성할 수 있음
- 서버 추가가 SSH key 준비와 Swarm join까지 자동화됨
- 서비스 생성은 YAML 없이 wizard로 가능
- 서비스 배포 후 nginx, 도메인, 인증서 상태가 한 화면에서 확인됨
- 도메인 관리에서 인증서 업로드와 만료일 확인 가능
- certbot 무료 인증서 발급이 서비스 화면에서 가능
- 로컬 이미지와 백업 이미지의 사용/미사용 여부를 관리 가능
- Job API와 Job UI가 사용자 흐름에서 제거됨
- Playwright가 최초 구성, 서버 추가, 서비스 생성, 도메인 연결, 백업 정리 핵심 흐름을 통과함
