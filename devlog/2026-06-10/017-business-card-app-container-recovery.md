# 명함관리 app 중지 컨테이너 기반 복구 이미지 적용

## 사용자 요청

- 리뷰 ID: `alpitwuiyzqcjojprsumwdaaiwbvnkrr`
- 제목: 서비스 생성 시 compose yaml 보완
- 요청 내용: 명함관리 서비스의 app 컨테이너는 볼륨 처리 없이 개발 내용이 컨테이너 내부에 남아 있으므로, 현재 중지된 컨테이너로 반드시 복구.

## 변경 파일

- `.runtime/dev/templates/bus_f7b72d/docker-compose.yaml`
- `devlog.md`
- `devlog/2026-06-10/017-business-card-app-container-recovery.md`

## 작업 내용

- mini3에서 중지된 `bus_f7b72d_app` 컨테이너 `a011affe99eb`를 복구 대상으로 확인했다.
- 해당 컨테이너를 mini3 로컬 이미지 `bus_f7b72d_app_recovered:20260610131540`로 커밋했다.
- `bus_f7b72d` compose의 app image를 복구 이미지로 변경했다.
- Swarm service `bus_f7b72d_app`을 `--no-resolve-image`로 복구 이미지에 업데이트했다.

## 확인 결과

- `bus_f7b72d_app` 현재 task가 mini3에서 `bus_f7b72d_app_recovered:20260610131540` 이미지로 Running.
- `bus_f7b72d_app`, `bus_f7b72d_db` 모두 replica `1/1`.
- service spec의 `DB_HOST=bus_f7b72d_db` 유지 확인.
- `http://172.16.0.226:3000` HTTP 200 응답 확인.

## 참고 사항

- 복구 이미지는 mini3 로컬 이미지이며 크기는 약 12.9GB다.
- 서비스는 mini3 node id 제약으로 고정되어 있어 로컬 이미지 기반으로 동작한다.
