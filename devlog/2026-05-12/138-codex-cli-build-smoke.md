# Codex CLI debug 빌드와 로컬 Responses smoke 테스트로 실행 리스크 보완

- 날짜: 2026-05-12
- ID: 138
- 리뷰 ID: hufvrianlhobxsyvrorjmbvwffdkjioy

## 사용자 원문 요청

남은 리스크들을 보완하고, 실제 동작도 가능하면 확인해줘.

## 변경 파일

- `devlog.md`
- `devlog/2026-05-12/138-codex-cli-build-smoke.md`

## 변경 내용

- 릴리스 빌드 SIGKILL 리스크를 줄이기 위해 `/swapfile-codex` 16GiB 스왑을 추가했다.
- 수정된 Codex CLI 소스를 `cargo build -p codex-cli -j 1`로 debug 빌드해 `/root/docker-infra/codex/codex-rs/target/debug/codex` 실행 파일을 생성했다.
- Docker Infra `codex_runtime.py`가 탐색하는 debug Codex 바이너리 경로를 실제로 채웠다.
- 외부 AI 토큰 없이 로컬 fake Responses API를 띄워 `codex exec --json --model-provider fake --output-last-message ...` 최소 실행을 검증했다.

## 확인 결과

- `/root/docker-infra/codex/codex-rs/target/debug/codex --version` 결과: `codex-cli 0.0.0`.
- `codex exec --help`에서 `--model-provider`, `--output-last-message`, `--json`, `--skip-git-repo-check` 옵션 확인.
- 로컬 fake Responses API smoke 테스트에서 `codex exec` 종료 코드 0, last-message 내용 `{"ok": true}` 확인.
- fake Responses API 서버는 테스트 후 종료했다.
- `python -m py_compile project/main/src/model/struct/codex_runtime.py project/main/src/model/struct/ai_assistant.py project/main/tools/docker_infra_mcp.py` 성공.
- `wiz_project_build(clean=false)` 성공.
