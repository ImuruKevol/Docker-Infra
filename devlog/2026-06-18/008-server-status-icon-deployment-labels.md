# 서버 상태 아이콘과 배포 방식 문구 정리

## 원 요청

- 대시보드의 서버 목록에서 `Active`/`Compose` 상태 배지를 IP 배지 오른쪽으로 옮기고, 텍스트/배지 대신 정상은 초록 체크 아이콘, 통신 불가 등 문제 상태는 빨간 경고 아이콘처럼 컴팩트하게 표시.
- `Swarm 배포`/`Compose 배포` 문구가 알아보기 어려우므로 `Swarm 배포`는 `클러스터`, `Compose 배포`는 독립적인 서버를 표현하는 단어로 변경.
- 동일한 표시를 서버 관리 목록과 서버 상세 화면에도 반영.

## 확인 및 변경 내용

- 대시보드 서버 목록
  - 서버명 옆 IP 배지 오른쪽에 상태 아이콘을 표시하도록 위치를 변경했다.
  - 기존 상태 텍스트 배지는 제거하고, 배포 방식 배지는 `클러스터`/`독립 서버`로 표시한다.
- 서버 관리 목록
  - Host 값 오른쪽에 상태 아이콘을 표시한다.
  - 기존 상태 배지를 제거하고 구성 컬럼에는 `클러스터`/`독립 서버`만 표시한다.
- 서버 상세 화면
  - IP 배지 오른쪽에 상태 아이콘을 배치했다.
  - 상세 헤더의 Swarm 연결 문구 조합을 단순화해 `클러스터`/`독립 서버` 배지만 표시한다.
- 상태 아이콘 기준
  - 정상 계열 상태는 초록 체크 아이콘으로 표시한다.
  - `unreachable`, `failed`, `error`, `canceled`는 빨간 경고 아이콘으로 표시한다.
  - `pending`, `degraded`, `warning`, `unknown`, `skipped` 또는 상태 없음은 주황 경고 아이콘으로 표시한다.

## 변경 파일

- `src/app/page.dashboard/view.pug`
- `src/app/page.dashboard/view.ts`
- `src/app/page.servers/view.pug`
- `src/app/page.servers/view.ts`
- `devlog.md`
- `devlog/2026-06-18/008-server-status-icon-deployment-labels.md`

## 검증 결과

- WIZ 빌드
  - 명령: `wiz_project_build(projectName="main", clean=false)`
  - 결과: 통과
- 잔여 문구 검색
  - 대상: `src/app/page.dashboard`, `src/app/page.servers`
  - 결과: 표시 문구로 `Swarm 배포`, `Compose 배포`, `Swarm 미연동`, `Swarm manager`, `Swarm 연결됨` 잔여 없음
- 요청 링크 브라우저 접근
  - URL: `https://infra-dev.nanoha.kr/dashboard`, `https://infra-dev.nanoha.kr/servers`
  - 쿠키: `season-wiz-project=main`, `season-wiz-devmode=true` 적용
  - 결과: 두 경로 모두 `/access`로 리다이렉트되어 인증 전 화면까지만 확인됨

## 남은 리스크

- 인증 비밀번호 환경변수가 없어 실제 운영 데이터가 들어간 대시보드/서버 상세 DOM까지는 브라우저로 확인하지 못했다.
