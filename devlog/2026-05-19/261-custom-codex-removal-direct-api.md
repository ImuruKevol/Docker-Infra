# 261. custom Codex 실행 경로 제거와 provider 직접 API 호출 전환

## 사용자 요청

커스텀 Codex 로직 제거 시 서비스 생성/수정/점검 시 사용하는 로직에 문제가 없도록 확실하게 신경써서 제거해야해. 작업 진행해줘.

## 변경 요약

- 공식 Codex 로그인 provider는 기존처럼 공식 `codex` CLI를 사용하고, OpenAI/Gemini/Ollama provider는 custom Codex CLI를 거치지 않고 각 HTTP API를 직접 호출하도록 변경했다.
- 직접 API 호출 경로에서도 서비스 생성/수정/점검에 필요한 Docker Infra 컨텍스트를 프롬프트에 포함하도록 보강했다.
- installer의 custom Codex 설치 단계, payload binary, runtime env, checksum, UI/API step 계약을 제거했다.
- 서비스 AI 진행 표시와 fallback 메시지에서 custom Codex CLI 표시를 제거하고 직접 API 호출 상태를 표시하도록 정리했다.

## 변경 파일

- `src/model/struct/codex_runtime.py`
- `src/model/struct/ai_assistant.py`
- `src/app/page.services.create/view.ts`
- `installer/install.sh`
- `installer/preinstall.sh`
- `installer/installer_api.py`
- `installer/installer.html`
- `installer/cleanup.sh`
- `installer/docker-infra.env.example`
- `installer/README.md`
- `installer/payload/checksums.sha256`
- `installer/payload/codex-bin/linux-x86_64/codex` 삭제
- `installer/payload/codex-bin/linux-aarch64/codex` 삭제
- `tests/api/test_installer_contract.py`
- `tests/api/test_services_preflight.py`
- `docs/docker-infra-deployment.md`
- `README.md`
- `/root/docker-infra/update-wiz-bundle.sh`
- `devlog.md`
- `devlog/2026-05-19/261-custom-codex-removal-direct-api.md`

## 확인 결과

- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/codex_runtime.py src/model/struct/ai_assistant.py tests/api/test_installer_contract.py tests/api/test_services_preflight.py installer/installer_api.py`: 통과
- `bash -n installer/install.sh`, `bash -n installer/preinstall.sh`, `bash -n installer/cleanup.sh`, `bash -n /root/docker-infra/update-wiz-bundle.sh`: 통과
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_installer_contract`: 통과
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_services_preflight`: 통과
- `wiz_project_build(projectName=main, clean=false)`: 통과
- runtime/installer/docs/tests 범위에서 custom Codex 사용 경로 문자열은 테스트의 부재 검증 항목으로만 남는 것을 확인했다.

## 남은 리스크

- 실제 OpenAI/Gemini/Ollama API 토큰과 모델을 사용한 외부 API 호출은 이번 검증에서 수행하지 않았다.
