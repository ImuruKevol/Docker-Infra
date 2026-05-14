# 202. 서비스 AI 검사 모달 모델 선택 배치 조정

- 날짜: 2026-05-14
- 요청: "모달에서 추가 코멘트 작성 부분은 세로로 길어질 수 있는데 그 오른쪽에 사용할 모델 select는 height가 정해져 있어서 레이아웃이 깨지는 것 같은 느낌을 받고 있어. 사용할 모델 select 부분은 추가 코멘트 아래쪽으로 옮겨줘."

## 변경 파일

- `src/app/page.services/view.pug`
- `devlog.md`
- `devlog/2026-05-14/202-service-ai-modal-model-placement.md`

## 작업 내용

- AI 백그라운드 검사/수정 모달의 상단 입력 영역을 2열 grid에서 세로 stack으로 변경했다.
- `사용할 모델` select가 `추가 코멘트` textarea 아래에 배치되도록 조정해 textarea 세로 확장 시 오른쪽 select와 높이 불균형이 보이지 않게 했다.

## 확인 결과

- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_services_preflight` 성공.
- `wiz_project_build(clean=false, projectName="main")` 성공.

## 남은 리스크

- 실제 브라우저에서 textarea를 크게 늘린 상태의 시각 확인은 수행하지 않았다.
