# 291. README/라이선스/installer 공개 준비

## 사용자 요청

리뷰 `rvabzbmpqkjtodfmelwrcmgdpnybbjcl` 기준으로 GitHub 공개 전 마무리 작업을 진행해 달라는 요청이었다. README를 현재 기준으로 갱신하고 한글/영어를 모두 작성하며, MIT LICENSE를 추가하고, installer를 현재 코드 기준으로 업데이트해야 했다. 진행 중 실제 관리자 비밀번호, SSH key 파일, token 같은 민감정보가 포함되지 않는지도 확인해야 했다.

## 변경 파일

- `README.md`: 현재 제품 범위, 핵심 기능, 운영 설치, 개발/검증, 보안 원칙을 한글/영어로 재작성.
- `LICENSE`: MIT License 추가. 요청받은 저작권자 이름, 닉네임, 이메일 표기 반영.
- `.gitignore`: 로컬 secret 파일과 private key 계열 파일이 실수로 추가되지 않도록 ignore 규칙 보강.
- `installer/README.md`: installer 목적, 단계, payload 갱신, cleanup, 보안 기준을 한글/영어로 갱신.
- `installer/install.sh`: PostgreSQL role password 설정 시 password 원문이 process argument에 남지 않도록 SQL을 표준 입력으로 전달하도록 수정.
- `docs/docker-infra-deployment.md`: 기준일 갱신 및 installer/문서/devlog 민감정보 처리 기준 추가.
- `installer/payload/wiz-bundle.tar.zst`: 현재 WIZ bundle 기준으로 installer payload 재생성.
- `installer/payload/checksums.sha256`: 갱신된 bundle checksum 반영.
- `devlog.md`, `devlog/2026-05-20/291-readme-license-installer-public-prep.md`: 작업 기록 추가.

## 민감정보 확인

- Git tracked file 목록에서 `config.env`, `domain.txt`, `.env`, SSH private key 이름, `*.pem`, `*.p12`, `*.key` 파일이 포함되지 않는 것을 확인했다.
- installer payload archive 목록에서 `config.env`, `domain.txt`, `.env`, SSH key/private key 확장자 파일이 포함되지 않는 것을 확인했다.
- 편집한 README, installer README, 배포 문서, installer script, checksum, LICENSE 범위에서 일반적인 private key/API token 패턴과 비어 있지 않은 secret env assignment가 없는 것을 확인했다.
- `src/model/struct/secret_masking.py`에 있는 private key 문자열은 실제 key가 아니라 마스킹 정규식 패턴임을 확인했다.
- `/root/docker-infra/config.env`, `/root/docker-infra/domain.txt`의 값은 출력하거나 문서/devlog에 기록하지 않았다.

## 검증

- `wiz_project_build(clean=false)`: 통과.
- `/opt/conda/envs/docker-infra/bin/wiz bundle --project=main`: 통과.
- `./update-wiz-bundle.sh`: 통과, payload checksum 검증 포함.
- `bash -n installer/preinstall.sh installer/install.sh installer/cleanup.sh /root/docker-infra/update-wiz-bundle.sh /root/docker-infra/update-wiz-service.sh`: 통과.
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests/api/test_installer_contract.py`: 11개 테스트 통과.
- `(cd installer/payload && sha256sum -c checksums.sha256)`: 통과.
