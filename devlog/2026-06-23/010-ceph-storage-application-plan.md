# CephFS Storage Docker Infra 적용 설계 문서 추가

## 사용자 요청

이제 이 문서를 바탕으로 실제 이 Docker Infra에 어떻게 적용을 해야할지, 어떤 화면에 어떤 기능을 추가해서 사용자가 어떤 흐름으로 관리를 해야할지 등을 상세하게 별도의 문서로 작성해줘.
어떤 기능들에 영향을 주고 수정이 되어야 하는지도 상세하게 분석이 되어야 해.

## 변경 파일

- `docs/ceph-storage-application-plan.md`
- `devlog.md`
- `devlog/2026-06-23/010-ceph-storage-application-plan.md`

## 작업 내용

- CephFS Storage를 Docker Infra에 실제 적용하기 위한 별도 설계 문서를 추가했다.
- 현재 화면 구조(`/dashboard`, `/services`, `/services/create`, `/servers`, `/system/backup`, `/operations`, 사이드바)를 기준으로 추가/변경할 기능을 정리했다.
- 신규 `/storage` 화면을 개요, 클러스터, OSD 슬롯, 서비스 저장소, 정책 탭으로 나누어 설계했다.
- 서비스 생성 wizard에서 named volume을 CephFS bind mount로 변환하는 사용자 흐름과 Compose 변환 규칙을 작성했다.
- 서비스 상세의 저장소 탭, 릴리즈 modal, 롤백 modal, CephFS snapshot 복원 흐름을 설계했다.
- 기존 Harbor/ORAS 기반 named volume 백업 기능은 legacy restore 전용으로 축소하고, 신규 기본 경로는 CephFS snapshot으로 전환하도록 정리했다.
- 영향을 받는 기존 모델, 화면, API, migration, 파일 트리, AI Agent, 템플릿, 설치 흐름을 파일 단위로 분석했다.
- 단계별 구현 계획과 UI/API/실동작 검증 계획을 추가했다.

## 검증 결과

- 문서 전용 변경이라 애플리케이션 빌드나 unit test는 실행하지 않았다.
- 기존 Ceph 설계 문서와 현재 서비스/서버/시스템/백업 관련 화면 및 모델 파일을 확인했다.
- `rg`로 새 문서에 `/storage`, `/servers`, `/services/create`, `/services`, `/system/backup`, `service_volume_backups`, `services_wizard`, `services_preflight`, `services_rollback`, `storage_snapshots`, CephFS, OSD, CRUSH, Harbor, ORAS, Phase 항목이 포함된 것을 확인했다.
- `wc -l`로 새 문서가 1668줄 규모로 작성된 것을 확인했다.

## 남은 리스크

- 아직 구현 문서만 추가했으며 실제 UI/API/DB migration은 만들지 않았다.
- Ceph daemon을 Swarm으로 직접 운영하는 방식은 PoC 전까지 device mapping, host network, ceph-volume 결과, 재시작 안정성 리스크가 남아 있다.
- 기존 ORAS named volume 백업과 신규 CephFS snapshot 체계를 동시에 유지하는 전환 기간의 호환 정책은 구현 시 더 세부적으로 확정해야 한다.
