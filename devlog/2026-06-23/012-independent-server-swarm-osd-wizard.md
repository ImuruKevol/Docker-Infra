# 독립 서버 보존과 Swarm OSD 구성 마법사 설계 반영

## 사용자 요청

이렇게 되면 현재 "독립 서버" 라는 형태로 들어간 개념이 삭제가 되어야겠네?
이왕이면 독립 서버에 대해서는 ceph 없이 돌아가는 형태로 놔두면 좋을 것 같은데, 이 내용이 문서들에 반영이 되어야 해.
그리고 서버 등록 후 Swarm 클러스터에 등록을 하고 나면 해당 서버에 ceph osd 슬롯을 웹 화면에서 만들 수 있도록 하는 구성 마법사 같은 기능이 있어야 해.

## 변경 파일

- `docs/backup-volume-layered-storage-design.md`
- `docs/ceph-storage-application-plan.md`
- `devlog.md`
- `devlog/2026-06-23/012-independent-server-swarm-osd-wizard.md`

## 변경 내용

- 독립 서버를 삭제하지 않고 Ceph 없이 local bind mount 또는 legacy named volume로 동작하는 경량 모드로 남기도록 설계에 반영했다.
- Swarm cluster에 등록된 서버만 Ceph OSD slot 대상이 되며, `swarm_node_id` 확인 후 OSD 슬롯 구성 마법사를 사용할 수 있도록 정리했다.
- `/servers`, `/storage`, `/services/create`, setup, 구현 단계, 위험 요소, 검증 계획에 독립 서버와 Swarm 서버의 분기 흐름을 추가했다.
- OSD 슬롯 구성 마법사의 단계, 활성 조건, preflight, plan 확인, ceph-volume prepare/activate, CRUSH host 검증 흐름을 문서화했다.

## 확인 결과

- `rg`로 두 설계 문서에 `독립 서버`, `OSD 슬롯 구성 마법사`, `swarm_node_id`, `local bind mount`, `클러스터 서비스` 반영 여부를 확인했다.
- 조건 없는 CephFS 기본값 표현을 검색해 독립 서버 예외와 충돌하지 않도록 수정했다.
- 문서 변경만 수행했으므로 빌드와 자동 테스트는 실행하지 않았다.

## 남은 리스크

- 실제 UI/API 구현은 아직 진행하지 않았다.
- OSD slot 생성은 디스크 partition/LV를 다루는 위험 작업이므로 PoC에서 rollback 불가 범위와 plan 표시를 별도로 검증해야 한다.
- 독립 서버의 local bind mount 데이터는 Ceph replica와 snapshot 보호를 받지 않으므로, Swarm 전환 시 migration wizard가 필요하다.
