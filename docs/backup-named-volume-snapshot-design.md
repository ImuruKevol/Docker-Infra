# Named Volume Snapshot Backup Design

> 상태: ORAS 기반 named volume archive 방식은 검증 결과 장기 최적화 방향으로는 보류한다. volume tar.gz를 OCI artifact 단일 blob으로 올리는 방식은 단순하지만, Docker image layer처럼 변경분만 효율적으로 누적하는 구조가 아니다. 향후 방향은 [Dockerized Ceph 기반 Bind Mount Storage 설계](backup-volume-layered-storage-design.md)를 우선 문서로 본다.

## 배경

현재 컨테이너 상태 스냅샷은 `docker commit`으로 컨테이너 파일시스템을 이미지화한 뒤 Harbor에 push한다. 이 방식은 컨테이너 writable layer만 보존하며, named volume에 저장된 데이터는 이미지에 포함되지 않는다. PostgreSQL, MySQL, Redis처럼 상태가 named volume에 저장되는 서비스는 이미지 스냅샷보다 volume 백업이 실제 복구 단위가 되는 경우가 많다.

## 목표

- 등록 서비스 기준으로 컨테이너 이미지 스냅샷과 named volume 백업을 분리해서 실행한다.
- 템플릿 생성 기본값은 컨테이너 스냅샷과 named volume 백업을 모두 포함하는 `full_state`로 한다.
- DB류 서비스는 설정에 따라 컨테이너 스냅샷 없이 named volume만 백업할 수 있게 한다.
- 자동 백업은 기본적으로 실행 중인 컨테이너 스냅샷과 해당 서비스의 named volume 백업을 같은 실행 묶음으로 생성한다.
- Agent가 템플릿을 생성하거나 수정할 때 백업 정책을 함께 제안하고, stateful 서비스가 백업 정책 없이 생성되지 않도록 한다.
- Harbor에는 컨테이너 이미지와 volume archive를 같은 서비스 백업 이력에서 추적하되, artifact kind를 구분한다.
- 서비스별 보존 개수는 이미지 스냅샷과 volume 백업 모두에 적용한다.
- target node에는 `oras` 설치를 필수 전제로 한다. 서버 관리에서 신규 서버 추가 시 `snap install oras --classic`을 실행하고, 백업 실행 중 `oras`가 없으면 fallback 없이 실패시킨다.

## 백업 단위

- `container_snapshot`: 현재 구현된 `docker commit` 기반 이미지 스냅샷.
- `named_volume_snapshot`: named volume을 tar/gzip archive로 묶은 OCI artifact.
- `service_state_snapshot`: 한 번의 실행에서 생성된 이미지 스냅샷과 volume 스냅샷 묶음. 기본값은 `container_snapshot + named_volume_snapshot`이며, 설정에 따라 `named_volume_snapshot`만 포함할 수 있다.

## 대상 탐지

1. Compose 파일의 top-level `volumes`와 각 service의 `volumes` mount를 파싱한다.
2. host bind mount는 초기 범위에서 제외하고 named volume만 대상으로 한다.
3. 실행 중인 컨테이너가 떠있는 node를 기준으로 volume 백업 명령을 실행한다.
4. volume 이름은 Compose project prefix가 붙은 실제 Docker volume 이름을 우선 사용하고, 찾지 못하면 Compose 선언 이름으로 fallback한다.

## 백업 정책 모델

템플릿, 서비스, 자동 백업 정책은 같은 의미의 백업 모드를 사용한다.

```yaml
x-docker-infra:
  backup:
    mode: full_state            # full_state | volume_only
    container_snapshot: true    # volume_only에서는 false
    named_volumes: true
    hooks:
      pre_freeze: []
      post_thaw: []
```

- `full_state`: 기본값. 컨테이너 스냅샷과 named volume archive를 모두 생성한다.
- `volume_only`: 컨테이너 이미지는 표준 이미지/태그를 그대로 쓰고 named volume만 백업한다. DB처럼 상태가 전부 volume에 있고 컨테이너 스냅샷 가치가 낮은 서비스에서만 선택한다.
- `container_snapshot: false`는 `named_volumes: true`와 함께 사용해야 한다. image-only 백업 모드는 지원하지 않는다.
- 자동 백업은 서비스별 정책이 없으면 `full_state`로 실행한다.
- 서비스별 정책은 템플릿 metadata, Compose extension field, 서비스 설정 UI 순으로 병합하되, UI에서 저장한 명시 설정이 가장 높은 우선순위를 가진다.

## 실행 방식

### 기본 volume archive

대상 node에서 임시 작업 디렉터리를 만들고 Docker 임시 컨테이너로 archive를 생성한다. OCI artifact push는 host에 설치된 `oras`만 사용한다.

```bash
docker run --rm \
  -v <volume_name>:/source:ro \
  -v <work_dir>:/backup \
  alpine:3.20 sh -lc 'cd /source && tar -czf /backup/<artifact>.tar.gz .'
```

archive 생성 후 host의 `oras push`로 Harbor에 OCI artifact로 업로드한다. `oras`가 없으면 자동 설치/fallback 없이 백업을 실패 처리한다.

```bash
oras push <registry>/<project>/volume-<service>-<volume>:<timestamp> \
  <artifact>.tar.gz:application/vnd.docker-infra.volume.layer.v1+gzip \
  --annotation docker-infra.kind=named_volume_snapshot
```

### ORAS 설치 정책

- 서버 관리 화면에서 신규 서버를 추가할 때 관리용 SSH key 등록 후 `snap install oras --classic`을 실행한다.
- 이미 설치되어 있으면 `command -v oras` 확인만 통과하고 설치는 건너뛴다.
- 자동 백업 preflight는 node별로 Docker 실행 가능 여부, `oras` 존재 여부, registry login 가능 여부를 확인한다.
- `oras`가 없거나 `snap install oras --classic`이 실패하면 `NODE_ORAS_INSTALL_FAILED` 또는 `SERVICE_VOLUME_BACKUP_ORAS_REQUIRED`로 실패시킨다.
- fallback push 경로는 두지 않는다. volume artifact는 반드시 target node의 `oras` 명령어로 Harbor에 push한다.

### DB 서비스 고려

- 기본값은 `full_state`이며, volume archive는 crash-consistent 방식이다.
- DB 템플릿에는 선택적으로 pre-freeze/post-thaw hook을 둘 수 있다.
- PostgreSQL/MySQL처럼 온라인 일관성이 중요한 서비스는 hook으로 checkpoint/flush/read lock을 실행하거나, 추후 logical dump 백업 타입을 별도로 추가한다.
- DB 서비스에서 이미지가 표준 이미지이고 상태가 전부 named volume에 있으면 운영자가 `volume_only` 정책으로 컨테이너 스냅샷을 생략할 수 있다.

## Agent 연동

Agent가 템플릿 생성, 서비스 생성, 런타임 수정 제안을 만들 때 다음 계약을 따른다.

- stateful service를 생성하면 반드시 backup policy를 함께 생성한다. named volume이 하나라도 있으면 기본값은 `mode: full_state`, `container_snapshot: true`, `named_volumes: true`다.
- 사용자가 DB/Redis처럼 volume 중심 백업을 원하거나 템플릿 옵션에서 컨테이너 스냅샷 제외를 선택한 경우에만 `mode: volume_only`, `container_snapshot: false`를 제안한다.
- Agent는 Compose의 named volume 선언과 service mount path를 추출해 `backup.volumes` 후보를 설명하고, bind mount는 초기 지원 범위 밖으로 표시한다.
- Agent는 DB 템플릿에 hook 후보를 제안하되, hook이 불확실하면 crash-consistent archive로 두고 사용자가 확인할 수 있게 한다.
- Agent가 생성한 템플릿에는 백업 정책 요약을 template metadata와 Compose extension field에 모두 남겨 UI/자동 백업이 같은 정책을 읽을 수 있게 한다.
- Agent 검증 단계는 named volume이 있는데 backup policy가 없거나, `container_snapshot: false`이면서 `named_volumes: false`인 템플릿을 실패로 처리한다.
- Agent 응답에는 "백업 정책" 항목을 포함해 `full_state`인지 `volume_only`인지, 컨테이너 스냅샷 제외 사유가 무엇인지 명시한다.

## 이력 모델

`service_image_backups`를 확장하거나 별도 `service_volume_backups` 테이블을 추가한다. 권장안은 별도 테이블이다.

- `service_id`, `compose_service`, `volume_name`, `node_id`, `container_id`
- `artifact_ref`, `artifact_status`, `artifact_size`
- `backup_kind = named_volume_snapshot`
- `snapshot_group_id`: 같은 실행에서 생성된 이미지/volume 묶음 식별자
- `metadata`: mount path, archive checksum, hook 결과

## 복구 방식

1. 대상 node에서 empty named volume을 생성한다.
2. Harbor에서 OCI artifact를 pull한다.
3. 임시 컨테이너로 archive를 volume에 extract한다.
4. Compose 파일의 image가 snapshot image를 사용해야 하는 경우에만 image ref를 교체한다.
5. `volume_only` 백업은 Compose image를 그대로 두고 volume만 복구한다.

## UI 정책

- 자동 백업 기본 모드는 `서비스 상태 스냅샷`으로 유지한다.
- 서비스별 상세 설정은 `컨테이너+volume`, `volume only`만 노출한다. image-only는 지원하지 않는다.
- DB 템플릿도 기본값은 `컨테이너+volume`이며, 템플릿 옵션 또는 서비스 설정에서 컨테이너 스냅샷 제외를 선택할 수 있게 한다.
- 진행 로그는 `서비스명 / compose 서비스 / volume명`까지 표시한다.
- 자동 백업 결과는 서비스 상세 버전 이력에 같은 `service_state_snapshot` 묶음으로 표시한다.

## 단계별 적용

1. Compose named volume 탐지와 백업 계획 preview 추가.
2. Agent 템플릿 생성 계약에 `full_state`/`volume_only` 정책과 검증 규칙 추가.
3. 서버 추가 시 `snap install oras --classic` 실행과 백업 실행 전 `oras` 필수 검증 추가.
4. node별 volume archive 생성 및 Harbor OCI artifact push 구현.
5. volume 백업 이력/보존 정책 연동.
6. restore flow 추가.
7. DB 템플릿별 hook 프리셋과 `volume_only` 정책 UI 추가.
