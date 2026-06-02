# 최신 기능 반영 installer WIZ bundle payload 갱신

- **ID**: 001
- **날짜**: 2026-05-28
- **유형**: 배포 패키지 갱신

## 작업 요약

최신 WIZ 빌드와 bundle 산출물을 생성한 뒤 installer payload의 `wiz-bundle.tar.zst`를 재생성했습니다. Compose healthcheck 선택 처리, 서비스 상세 fast path, 템플릿 AI, DDNS/nginx 보강 등 최근 앱 변경분이 installer 설치 archive에 포함되도록 checksum도 함께 갱신했습니다.

## 원문 요청사항

```text
작업 시작

리뷰 ID: ypzjhxgqapotajsijpknghcxcyszyhra
제목: installer 갱신

이전에 만든 installer가 있긴 한데, 기능이 조금 더 업데이트되고 바뀐 부분들이 있어서 installer를 갱신해야해.
```

## 변경 파일 목록

- `installer/payload/wiz-bundle.tar.zst`: 최신 `main` WIZ bundle 기준으로 installer payload archive 재생성.
- `installer/payload/checksums.sha256`: 갱신된 archive checksum 반영.
- `devlog.md`, `devlog/2026-05-28/001-installer-wiz-bundle-refresh.md`: 작업 이력 기록.

## 검증 결과

- `wiz_project_build(projectName="main", clean=false)` 성공.
- `/opt/conda/envs/docker-infra/bin/wiz bundle --project=main` 성공.
- `./update-wiz-bundle.sh` 성공, payload checksum 검증 포함.
- `tar --zstd -tf project/main/installer/payload/wiz-bundle.tar.zst | rg 'services_detail_fast|template_ai|compose_validator.py|page.services/api.py'`로 최신 기능 관련 파일 포함 확인.
- `(cd project/main/installer/payload && sha256sum -c checksums.sha256)` 성공.
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests/api/test_installer_contract.py` 성공, 11개 테스트 통과.
- `bash -n installer/preinstall.sh installer/install.sh installer/cleanup.sh /root/docker-infra/update-wiz-bundle.sh /root/docker-infra/update-wiz-service.sh` 성공.

## 남은 리스크

- 실제 신규 서버에서 `preinstall.sh`부터 전체 설치를 수행하는 검증은 이번 작업 범위에서 실행하지 않았습니다.
