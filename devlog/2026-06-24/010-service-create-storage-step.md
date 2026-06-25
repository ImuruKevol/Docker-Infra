# 서비스 생성 Wizard 저장소 확인 단계와 bind mount 자동 변환 연결

## 사용자 요청

작업 시작. 저장소 단계를 추가하되, 사용자가 뭘 복잡하게 설정하는건 절대 안되고, 사용자는 최대한 그냥 확인만 하고 넘어갈 수 있도록 자동화가 되어서 적용이 되어야 해.

## 변경 파일

- `src/app/page.services.create/api.py`
- `src/app/page.services.create/view.ts`
- `src/app/page.services.create/view.pug`
- `src/model/struct/services_wizard.py`
- `src/model/struct/services_preflight.py`
- `src/model/struct/storage_mounts.py`
- `tests/api/test_storage_models.py`
- `tests/api/test_services_preflight.py`
- `devlog.md`
- `devlog/2026-06-24/010-service-create-storage-step.md`

## 변경 내용

- `/services/create`에 저장소 확인 섹션을 추가해 Docker-managed volume 후보, 실행 대상, 기본 저장 방식, 변환될 bind mount 경로를 자동 preview로 표시했다.
- 생성 Wizard API에 `storage_preview`를 추가해 최종 생성과 같은 `storage_mounts.normalize_compose()` 경로로 CephFS/local bind mount 계획을 계산하게 했다.
- Swarm/Ceph 정상 상태는 CephFS bind mount를 기본으로, 독립 서버 또는 Ceph 미구성/비정상 상태는 local bind mount를 기본으로 선택하게 했다.
- Ceph 미구성 fallback은 차단하지 않고 `스토리지 설정` 이동과 `local로 계속` 확인 액션을 제공한다.
- 저장 전 top-level `volumes:`를 제거하고 원래 volume 이름은 storage metadata/mount row 계획에 남기도록 normalizer를 보강했다.
- preflight에 local fallback 경고와 DB 데이터 경로 snapshot hook 권장 경고를 추가했다.

## 확인 결과

- `wiz_project_build(projectName=main, clean=false)` 통과.
- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/storage_mounts.py src/model/struct/services_wizard.py src/model/struct/services_preflight.py src/app/page.services.create/api.py` 통과.
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_storage_models.StorageModelStaticContractTest.test_storage_mount_normalizer_removes_docker_managed_volumes tests.api.test_storage_models.StorageModelStaticContractTest.test_cephfs_host_mount_and_service_mount_contract` 통과.
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_services_preflight.ServicesPreflightStaticContractTest.test_service_create_preflight_contract_is_wired` 통과.
- 참고: `tests/api/test_storage_models.py tests/api/test_services_preflight.py` 전체 실행은 이번 변경과 무관한 `page.templates` 정적 계약의 `templateAiModalOpen` 누락에서 실패했다.
