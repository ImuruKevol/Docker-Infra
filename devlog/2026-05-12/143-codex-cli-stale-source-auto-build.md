# Codex CLI 소스 변경 감지 기반 cargo 자동 빌드 보강

## 원 요청

서버에 cargo를 설치해놨어. 필요하면 알아서 빌드한 후 사용하도록 해줘.

## 변경 파일

- `src/model/struct/codex_runtime.py`
  - Codex CLI 실행 파일이 존재하더라도 `codex-rs` 소스가 더 최신이면 자동으로 `cargo build -p codex-cli --bin codex`를 실행하도록 보강.
  - 매 AI 호출마다 불필요하게 빌드하지 않도록 60초 빌드 확인 간격을 추가.
  - 자동 빌드 실패 시 오래된 바이너리를 묵시적으로 사용하지 않고 `CODEX_BUILD_FAILED`로 원인을 반환하도록 변경.
- `tests/api/test_services_preflight.py`
  - 소스 최신성 검사와 빌드 확인 간격 계약을 정적 테스트에 반영.

## 확인 결과

- `cargo --version`
  - `cargo 1.95.0`
- `cargo build -p codex-cli --bin codex`
  - 성공, dev profile 증분 빌드 완료
- `/root/docker-infra/codex/codex-rs/target/debug/codex --version`
  - `codex-cli 0.0.0`
- `python -m py_compile src/model/struct/codex_runtime.py tests/api/test_services_preflight.py`
  - 성공
- `python -m unittest tests.api.test_services_preflight`
  - 11개 테스트 성공
- 런타임 import smoke
  - `cargo=/root/.cargo/bin/cargo`
  - `resolved=/root/docker-infra/codex/codex-rs/target/debug/codex`
  - 잘못된 `DOCKER_INFRA_CODEX_BIN=/missing/codex`에서도 동일 바이너리로 fallback 확인
- `wiz_project_build(projectName=main, clean=false)`
  - 성공

## 남은 리스크

- `codex-rs` 소스가 변경된 직후 첫 AI 요청은 증분 빌드 시간만큼 지연될 수 있다.
- cargo 빌드 자체가 실패하면 오래된 바이너리를 사용하지 않고 에러를 반환하므로, 빌드 로그 확인이 필요하다.
