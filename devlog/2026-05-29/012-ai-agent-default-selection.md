# 다중 AI Agent 기본 선택 설정 추가

## 원 요청

AI Agent 사용이 여러 개가 되어있다면 AI 탭 상단에 기본으로 사용할 AI Agent를 선택할 수 있도록 해줘.

## 변경 파일

- `src/model/struct/ai_settings.py`
- `src/model/struct/ai_assistant.py`
- `src/app/page.system/api.py`
- `src/app/page.system/view.ts`
- `src/app/page.system/view.pug`
- `tests/api/test_system_settings_dynamic_menu.py`
- `tests/api/test_services_preflight.py`
- `installer/payload/wiz-bundle.tar.zst`
- `installer/payload/checksums.sha256`
- `devlog.md`
- `devlog/2026-05-29/012-ai-agent-default-selection.md`

## 변경 내용

- AI 설정에 `default_agent`를 추가하고, 사용 중인 Agent 중에서만 기본값이 유지되도록 정규화했다.
- AI 탭 상단에 사용 중인 Agent가 2개 이상일 때만 기본 AI Agent 검색 선택 UI와 저장 버튼을 표시하도록 했다.
- 서비스 생성, 템플릿 생성, 런타임 수정 등 AI 실행의 기본 Agent 선택이 저장된 `default_agent`를 우선 사용하도록 했다.
- 시스템 설정 API에 기본 Agent 단독 저장 엔드포인트를 추가했다.

## 확인 결과

- `python -m py_compile src/model/struct/ai_settings.py src/model/struct/ai_assistant.py src/app/page.system/api.py`
- `python -m unittest tests/api/test_services_preflight.py tests/api/test_system_settings_dynamic_menu.py tests/api/test_installer_contract.py`
- WIZ build 성공
- `/opt/conda/bin/wiz bundle --project=main`
- `/root/docker-infra/update-wiz-bundle.sh`
- `cd installer/payload && sha256sum -c checksums.sha256`
- `season-wiz-project=main`, `season-wiz-devmode=true` 쿠키로 `/dashboard`, `/system` HTTP 200 확인
