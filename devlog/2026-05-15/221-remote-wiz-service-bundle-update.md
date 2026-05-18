# 221. WIZ root bundle 업데이트 스크립트 단순화

- 날짜: 2026-05-15
- 리뷰 ID: bvcqctgclsqxedoxoqlotzzgmctpytup
- 프로젝트: main

## 원 요청

```text
스크립트가 쓸데없이 너무 어렵게 되어있어. 내가 wiz root(/root/docker-infra)에다가 update-wiz-bundle.sh를 옮겨놓고 좀 수정을 했는데, 이 정도 레벨로 스크립트를 단순화해줘.
update-wiz-service.sh도 wiz root로 옮겨놨어. 이것들은 굳이 installer 디렉토리 안에 있을 필요가 없어.
```

## 변경 파일

- `/root/docker-infra/update-wiz-bundle.sh`
- `/root/docker-infra/update-wiz-service.sh`
- `installer/README.md`
- `docs/docker-infra-deployment.md`
- `README.md`
- `tests/api/test_installer_contract.py`
- `devlog.md`
- `devlog/2026-05-15/221-remote-wiz-service-bundle-update.md`

## 작업 내용

- `update-wiz-bundle.sh`와 `update-wiz-service.sh`를 installer 하위가 아니라 WIZ root 기준 스크립트로 정리했다.
- `update-wiz-service.sh`를 archive extract, rsync 배포, `wiz.docker-infra.service` stop/start만 수행하는 단순한 흐름으로 줄였다.
- installer가 update helper를 설치하거나 cleanup하는 연결을 제거하고, 문서와 테스트도 WIZ root script 기준으로 수정했다.

## 확인 결과

- `bash -n`으로 WIZ root scripts와 installer shell scripts 구문 검사 통과
- `sha256sum -c checksums.sha256` 통과
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_installer_contract` 통과, 11개 실행
- `git diff --check` 통과

## 남은 리스크

- 실제 원격 운영 서버에서 `sudo ./update-wiz-service.sh /tmp/wiz-bundle.tar.zst` 실행 검증은 하지 않았다.
