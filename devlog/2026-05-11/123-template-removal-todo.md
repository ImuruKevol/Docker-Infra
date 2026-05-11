# 123. 템플릿 기능 제거 TODO 문서 추가

- 날짜: 2026-05-11
- 요청: "템플릿 기능을 제거하기 위한 TODO 문서를 작성해줘. 기존에 작성했던 TODO 문서가 있으니 포맷은 그 문서들을 참고해서 별도의 문서로 작성하면 돼. 템플릿 기능을 제거하고 현재 템플릿 관리에 들어가있는 AI 관련 프롬프트 및 설정 등은 잘 돌아가고 있던거라서 서비스 관리에서도 그대로 잘 써먹어야해. DB 및 백엔드 등에서도 확실하게 템플릿 기능을 제거해야하니 이 부분도 고려해서 TODO 문서를 작성해줘"

## 작업 내용

템플릿/기본 구성 제품 개념을 제거하고 서비스 생성을 AI 초안, Compose 직접 작성, 기존 Compose 가져오기 흐름으로 단순화하기 위한 별도 TODO 문서를 추가했다.

문서에는 다음 범위를 포함했다.

- 사용자 흐름 재정의
- 서비스 생성 API의 `template_id` 제거
- 템플릿 관리 AI 초안 기능을 서비스 초안 기능으로 이전하는 작업
- `templates`, `template_versions`, `setup.template_root` 등 DB/backend 제거 작업
- `/templates` 화면, nav, 번역 제거 작업
- 서비스 compose version/운영 메모로 대체할 범위
- 문서/OpenAPI/테스트 정리
- legacy 서비스와 runtime 경로 마이그레이션 고려사항
- 최종 검증 체크리스트

## 변경 파일

- `docs/template-removal-todo.md`
- `devlog.md`
- `devlog/2026-05-11/123-template-removal-todo.md`

## 검증

- 기존 TODO 문서 포맷을 확인했다.
- 템플릿 관련 UI, API, AI assistant, DB migration, setup/root, 테스트 참조를 검색해 문서 범위에 반영했다.
- 문서 추가 작업으로 애플리케이션 코드는 변경하지 않아 빌드는 실행하지 않았다.
