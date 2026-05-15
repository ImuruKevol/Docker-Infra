# 220. installer WIZ bundle payload 갱신 관리 스크립트 추가

- 날짜: 2026-05-15
- 리뷰 ID: bvcqctgclsqxedoxoqlotzzgmctpytup
- 프로젝트: main

## 원 요청

```text
Docker Infra 배포를 위한 installer에서 다른 것들은 괜찮은데, wiz-bundle.tar.zst는 현재 코드로 업데이트 하는 관리용 스크립트가 필요해.
```

## 변경 파일

- `installer/update-wiz-bundle.sh`
- `installer/payload/wiz-bundle.tar.zst`
- `installer/payload/checksums.sha256`
- `installer/README.md`
- `docs/docker-infra-deployment.md`
- `README.md`
- `tests/api/test_installer_contract.py`
- `devlog.md`
- `devlog/2026-05-15/220-installer-wiz-bundle-update-script.md`

## 작업 내용

- 개발 workspace에서 WIZ project build와 `wiz bundle`을 실행한 뒤 installer의 `payload/wiz-bundle.tar.zst`를 재생성하는 관리 스크립트를 추가했다.
- 스크립트가 payload checksum 파일을 다시 쓰고 `sha256sum -c`로 검증하도록 해 bundle 갱신 후 installer 무결성 검증이 이어지게 했다.
- 문서와 installer 계약 테스트에 bundle 갱신 절차와 checksum 일치 검증을 추가했다.
- 현재 코드 기준으로 `wiz-bundle.tar.zst`를 재생성하고 checksum 파일을 갱신했다.

## 확인 결과

- `bash -n installer/preinstall.sh installer/install.sh installer/cleanup.sh installer/update-wiz-bundle.sh` 통과
- `./installer/update-wiz-bundle.sh` 통과
- `sha256sum -c checksums.sha256` 통과
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_installer_contract` 통과, 10개 실행
- `git diff --check` 통과

## 남은 리스크

- 실제 운영 host 설치 경로에서는 갱신된 installer payload로 `install.sh --step bundle`을 실행해야 배포 파일 교체까지 최종 확인된다.
