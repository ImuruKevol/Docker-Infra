# 099. digest 포함 로컬 이미지 삭제 보강과 odoo 이미지 실제 삭제

## 요청 원문

로컬 이미지 삭제 기능이 동작하지 않아. 다시 확인해줘.
odoo 이미지는 실제로 삭제해도 돼

## 변경 파일

- `src/model/struct/images_shared.py`
- `src/model/struct/images_local.py`
- `tests/api/test_images_templates_catalog.py`

## 원인

- 로컬 Docker 목록에는 `odoo` `18`로 표시되지만 실제 inspect 결과의 RepoTag가 `odoo:18@sha256:...` 형태였다.
- 이 상태에서는 `docker image rm -f odoo:18`이 `No such image: odoo:18`을 반환할 수 있다.
- 기존 UI/API는 `repository:tag`를 삭제 참조로 보내고 있었기 때문에 digest가 포함된 로컬 이미지 행에서 삭제가 실패했다.

## 작업 내용

- Docker image 목록 파싱 시 digest가 있는 행은 삭제 참조를 `repository:tag@digest` 형식으로 만들도록 수정했다.
- 사용자가 이미 열린 화면에서 이전 `repository:tag` 참조로 삭제하더라도, 백엔드가 현재 이미지 목록을 다시 조회해 `repository:tag@digest`, `repository@digest`, image id 순으로 fallback 삭제를 시도하도록 보강했다.
- local-master 로컬 이미지 삭제는 기존 allowlist 기반 local executor 경로를 유지하고, 원격 서버도 `docker image rm -f`를 사용하도록 유지했다.
- `odoo:18` 이미지는 실제 image id `sha256:b79d87a4ec1a3806d133e12a07dc06402fc37397eb285663b1acfea2001ae52c` 기준으로 삭제했다.

## 검증

- `docker image rm -f odoo:18` 실패 재현: `No such image: odoo:18`
- `docker image rm -f sha256:b79d87a4ec1a3806d133e12a07dc06402fc37397eb285663b1acfea2001ae52c` 성공
- `docker image ls --digests --no-trunc --format '{{json .}}' | rg -i '"Repository":"odoo"|odoo'` 결과 없음
- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/images_shared.py src/model/struct/images_local.py`
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_images_templates_catalog.ImagesTemplatesStaticContractTest tests.api.test_node_reporter.NodeReporterStaticContractTest tests.api.test_services_preflight.ServicesPreflightStaticContractTest tests.api.test_server_macros.ServerMacrosStaticContractTest`
- `wiz_project_build(projectName="main", clean=false)`

## 비고

- `docker system df -v`에 `odoo_8b3acf_odoo_data`, `odoo_8b3acf_postgres_data` 볼륨 이름은 남아 있다. 이번 요청 범위는 이미지 삭제라 볼륨은 삭제하지 않았다.
