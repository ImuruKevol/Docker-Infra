# GlusterFS 설계 내용 제거와 CephFS 적용 작업 지시서 작성

## 사용자 요청

그럼 일단 설계 문서에서 글러스터 관련 내용은 전부 제거해줘.
그리고 ceph-storage-application-plan.md 문서를 기반으로 실제 Docker Infra에 적용하기 위한 작업 지시서를 작성해줘.
이 reviewops에 title, body만 바로 복사할 수 있도록 정리하고, 각 body에는 설계 문서나 plan 문서의 어디를 참고하라는 reference를 모두 참고하게 해야해.
이 때 각 body는 1000자가 넘지 않게 컴팩트하고 깔끔하게 정리해야해.

## 변경 파일

- `docs/backup-volume-layered-storage-design.md`
- `docs/ceph-storage-application-plan.md`
- `docs/ceph-storage-reviewops-task-instructions.md`
- `devlog.md`
- `devlog/2026-06-23/015-ceph-storage-reviewops-task-instructions.md`

## 변경 내용

- 설계 문서 2개에서 GlusterFS 관련 섹션과 Phase 문구를 제거했다.
- `ceph-storage-application-plan.md` 기반으로 ReviewOps 복사용 작업 지시서 문서를 추가했다.
- 작업 지시서는 12개 항목으로 구성했고, 각 항목은 `Title`, `Body` 형태로 정리했다.
- 각 Body 내부에 관련 설계 문서와 적용 계획 문서의 참고 섹션을 포함했다.

## 확인 결과

- `rg`로 설계 문서와 작업 지시서에 `Gluster`, `gluster`, `글러스터` 문구가 남지 않았음을 확인했다.
- `/opt/conda/envs/docker-infra/bin/python`으로 각 Body 길이가 reference 포함 1000자 이하임을 확인했다.
- 문서 변경만 수행했으므로 빌드와 자동 테스트는 실행하지 않았다.

## 남은 리스크

- 작업 지시서는 구현 단위 제안이며 실제 UI/API 구현은 아직 진행하지 않았다.
- ReviewOps 등록 시 우선순위와 담당자 배정은 별도로 결정해야 한다.
