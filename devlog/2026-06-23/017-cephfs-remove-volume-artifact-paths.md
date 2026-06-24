# CephFS 전환 시 volume artifact 경로 제거 정책 반영

## 사용자 요청

CephFS를 적용하면 oras와 named volume 부분은 완전히 삭제되어야 한다. 이미 배포되어 등록된 서비스는 수동 백업/재배포하거나 별도 Codex agent로 마이그레이션해도 된다. 부족한 내용을 설계 문서, plan 문서, 작업 지시서 문서에 모두 반영하고, 작업 지시서만 따라도 설계와 plan 의도대로 Docker Infra가 동작하도록 정리해달라.

## 변경 파일

- `docs/backup-volume-layered-storage-design.md`
- `docs/ceph-storage-application-plan.md`
- `docs/ceph-storage-reviewops-task-instructions.md`
- `docs/ceph-storage-implementation-feasibility-review.md`
- `devlog.md`
- `devlog/2026-06-23/017-cephfs-remove-volume-artifact-paths.md`

## 변경 내용

- Harbor는 image 전용으로 유지하고 서비스 데이터는 CephFS/local bind mount로만 관리하도록 설계 문서를 보강했다.
- 신규/수정/import 경로에서 Docker-managed volume 입력은 저장 전에 CephFS 또는 local bind mount로 변환하고, top-level `volumes:`가 남지 않아야 한다는 정책을 명시했다.
- 기존 배포 서비스의 Docker-managed volume은 제품에서 자동 이전하지 않고, 운영자가 직접 백업/재배포하거나 별도 Codex agent 작업으로 처리한다는 기준을 반영했다.
- 기존 volume artifact 백업/복원, scheduler volume backup, rollback volume restore, cleanup, 관련 설치 안내를 제품 호출에서 제거하는 작업 지시를 추가했다.
- ReviewOps 작업 지시서의 각 body가 1000자 이하를 유지하면서 설계/plan reference를 따르도록 조정했다.

## 확인 결과

- 대상 문서에서 `ORAS`, `oras`, `named volume`, `named_volume`, `legacy`, `Legacy`, `migration wizard`, `Migration Wizard`, `마이그레이션` 표현이 남아 있지 않음을 확인했다.
- ReviewOps 작업 지시서의 각 body 길이가 모두 1000자 이하임을 확인했다.
- 문서 변경만 수행했으므로 애플리케이션 빌드나 UI 테스트는 실행하지 않았다.

## 남은 리스크

- 실제 코드에서 기존 volume artifact 호출 제거와 Docker-managed volume 저장 차단은 아직 구현되지 않았다.
- 기존 배포 서비스 데이터 이동은 제품 자동 기능이 아니므로 운영 절차 또는 별도 Codex agent 작업으로 다뤄야 한다.
