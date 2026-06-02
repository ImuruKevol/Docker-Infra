# AI Agent Markdown 렌더링과 히스토리 상세 복사 UX 개선

- **ID**: 005
- **날짜**: 2026-06-01
- **유형**: 개선

## 작업 요약
채팅과 히스토리 상세의 Markdown 렌더링 결과를 `SafeHtml`로 명시 처리해 원문이 그대로 노출되는 문제를 방지했다.
코드 펜스가 없는 셸 명령 묶음도 코드블럭으로 감지하고, 채팅/히스토리 공통 코드블럭 스타일을 강화했다.
히스토리 목록은 질문 기반 제목만 보이도록 줄이고, 상세의 다음 동작은 채팅 실행 UI와 분리해 복사 버튼만 제공하도록 변경했다.
다음 동작 복사 완료 시 모달 대신 복사 아이콘이 잠시 체크 아이콘으로 바뀌도록 처리했다.

## 원문 요청사항
```text
채팅에서 마크다운 원문으로 표시되고 있어. 히스토리 상세에서도 그렇고.
그리고 히스토리에서 목록은 각 히스토리별 실제 내용은 목록에 보여주지 말고 목록에는 제목만 표시해줘.
그리고 채팅과 히스토리 상세에 코드블럭에 대한 부분도 스타일을 추가해줘.
히스토리 상세에서 다음 동작은 채팅창과 같은 형식으로 표시되면 안되고, 각 동작별로 복사하기 버튼만 있어야 해. 복사하기 버튼을 누르면 모달로 완료가 뜨지 말고 체크 아이콘으로 바뀌었다가 잠시 후에 되돌아가야 하고.
```

## 변경 파일 목록
- `src/angular/app/app.component.ts`: `DomSanitizer` 기반 Markdown HTML 반환, 명령어 코드블럭 감지, 히스토리 제목/복사 상태 처리 추가.
- `src/angular/app/app.component.pug`: 히스토리 목록을 제목 중심으로 축소하고, 상세 다음 동작을 복사 전용 UI로 변경.
- `src/angular/app/app.component.scss`: 코드블럭 스타일과 히스토리 상세 복사 목록/버튼 스타일 추가.
- `tests/api/test_ai_agent_history.py`: Markdown 렌더링, 코드블럭, 히스토리 제목/복사 UI 정적 계약 추가.
- `devlog.md`, `devlog/2026-06-01/005-ai-agent-markdown-history-copy.md`: 작업 이력 기록.

## 검증 결과
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_ai_agent_history` 성공.
- `git diff --check` 대상 파일 검사 성공.
- `wiz_project_build(clean=false)` 성공.
