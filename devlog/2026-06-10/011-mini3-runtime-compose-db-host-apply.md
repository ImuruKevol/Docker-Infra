# mini3 런타임 서비스 Compose DB host 보정 적용

## 사용자 요청

- 리뷰 ID: `alpitwuiyzqcjojprsumwdaaiwbvnkrr`
- 제목: 서비스 생성 시 compose yaml 보완
- 요청 내용: mini3 서버에 떠 있는 `SimpleSAMLphp TEST`, `명함 관리 서비스`의 compose yaml도 수정하고, 볼륨은 유지한 채 다시 적용.

## 변경 파일

- `.runtime/dev/templates/bus_f7b72d/docker-compose.yaml`
- `devlog.md`
- `devlog/2026-06-10/011-mini3-runtime-compose-db-host-apply.md`

## 변경 내용

- `명함 관리 서비스`로 확인된 `bus_f7b72d` compose에서 `app.DB_HOST`를 `db`에서 `bus_f7b72d_db`로 변경했다.
- `SimpleSAMLphp TEST`의 `simplesamlphp_test_ae291d` compose는 이미 `app.DB_HOST=simplesamlphp_test_ae291d_db`로 보정되어 있어 파일 변경 없이 재적용했다.
- 두 stack 모두 `docker stack deploy --with-registry-auth --prune`로 현재 compose를 다시 적용했다.

## 확인 결과

- YAML 파싱 확인: `bus_f7b72d`는 `app.DB_HOST=bus_f7b72d_db`, `simplesamlphp_test_ae291d`는 `app.DB_HOST=simplesamlphp_test_ae291d_db`.
- Docker service spec 확인: `bus_f7b72d_app`, `simplesamlphp_test_ae291d_app` 모두 분리된 `DB_HOST` 값을 사용.
- Replica 확인: `bus_f7b72d_app`, `bus_f7b72d_db`, `simplesamlphp_test_ae291d_app`, `simplesamlphp_test_ae291d_db` 모두 `1/1`.
- 참고: `bus_f7b72d_db`는 강제 갱신 중 기존 DB 파일 lock으로 한 차례 실패했고, 최종 replica는 `1/1`로 복구됐지만 Docker `UpdateStatus`에는 `rollback_paused` 이력이 남아 있다.
