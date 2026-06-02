# 원격 서버 최신 Docker Infra 재설치

- **ID**: 002
- **날짜**: 2026-05-28
- **유형**: 배포 작업

## 작업 요약

원격 서버 `172.16.3.96`에 최신 installer payload를 전송하고, 기존 Docker Infra 설치를 최신 bundle 기준으로 재설치했습니다. 기존 DB와 설정은 유지하면서 migration `019`, `020`을 적용했고 WIZ systemd service와 nginx reverse proxy를 최신 배포 파일로 갱신했습니다.

## 원문 요청사항

```text
아래 서버에 옛날 버전의 docker infra가 구축되어 있어. 아래 서버에 최신 버전으로 재설치해줘.
---
root@172.16.3.96
password: [REDACTED]
```

## 변경 파일 목록

- 원격 `/opt/docker-infra/wiz/`: 최신 `installer/payload/wiz-bundle.tar.zst` 내용으로 WIZ bundle 재배포.
- 원격 `/etc/docker-infra/docker-infra.env`: installer가 기존 DB/secret 값을 보존해 runtime env 재작성.
- 원격 `/etc/systemd/system/wiz.docker-infra.service`: WIZ service 재등록 및 drop-in env 적용.
- 원격 nginx site: Docker Infra reverse proxy 재적용.
- 원격 installer artifact: 설치 검증 후 `/opt/docker-infra/installer`와 임시 전송 파일 정리.
- `devlog.md`, `devlog/2026-05-28/002-remote-server-reinstall.md`: 작업 이력 기록.

## 검증 결과

- 원격 installer payload `sha256sum -c checksums.sha256` 성공.
- `/opt/docker-infra/installer/install.sh --step node` 성공, 공식 Codex CLI `/usr/bin/codex` 설치 확인.
- `/opt/docker-infra/installer/install.sh --step bundle/migrate/service/setup/nginx/verify` 순차 실행 성공.
- `/api/system/health`가 HTTP 200, DB `schema_version=020` 반환.
- `/api/system/setup`이 `configured=true`, `requires_setup=false` 반환.
- `/dashboard` HTTP 200 확인.
- 원격 bundle에서 `services_detail_fast.py`, `template_ai.py` 포함과 `HEALTHCHECK_REQUIRED` 제거 상태 확인.
- `wiz.docker-infra.service`와 `nginx`는 active, `docker-infra-installer.service`는 inactive 확인.

## 특이사항 및 남은 리스크

- 첫 `install.sh --step all` 실행은 Ubuntu unattended-upgrade의 dpkg/apt lock 때문에 중단되어 lock 해제 후 나머지 단계를 재실행했습니다.
- unattended-upgrade가 Raspberry Pi kernel을 갱신해 서버에 pending kernel upgrade 경고가 남았습니다. 최신 kernel 적용에는 별도 재부팅이 필요합니다.
