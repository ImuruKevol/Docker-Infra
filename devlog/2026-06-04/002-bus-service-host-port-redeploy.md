# bus 서비스 host-mode 포트 보정 배포

- 날짜: 2026-06-04
- 리뷰 ID: tpuvsgrpgzkejzmhuhyaztqjynkcdwfp
- 요청: "bus" 서비스에 대해서 정상적으로 서비스가 뜨도록 수정 및 보정 작업을 진행해줘.

## 변경 파일

- `.runtime/dev/templates/bus_f7b72d/docker-compose.yaml`
- `devlog.md`
- `devlog/2026-06-04/002-bus-service-host-port-redeploy.md`

## 작업 내용

- `bus_f7b72d` Compose의 app 서비스 `deploy.update_config.order`를 `start-first`에서 `stop-first`로 보정했다.
- 보정된 Compose로 `docker stack deploy --with-registry-auth --prune`를 실행해 실제 Swarm 서비스에 반영했다.

## 확인 결과

- `bus_f7b72d_app` 업데이트 상태가 `completed`로 전환됐다.
- `bus_f7b72d_app`과 `bus_f7b72d_db`가 모두 `1/1` 상태다.
- app 작업이 `mini3`에서 Running이며 published 포트가 `3000 -> 3000`, `55561 -> 22`로 반영됐다.
- `http://bus.sub.nanoha.kr`는 HTTP 200으로 응답했다.
- `http://172.16.0.226:3000`는 HTTP 200으로 응답했다.
- `172.16.0.226:55561` TCP 연결이 성공했다.
- WIZ API 상태 갱신 호출은 인증 세션 부재로 401 `AUTHENTICATION_REQUIRED`가 반환됐다.
