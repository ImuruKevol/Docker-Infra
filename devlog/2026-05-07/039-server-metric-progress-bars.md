# 서버 상세 CPU/Memory/Storage 프로그레스바와 부드러운 갱신 애니메이션 추가

- 날짜: 2026-05-07
- ID: 039

## 사용자 요청

- 서버 상세 상단의 CPU, Memory, Storage 카드에 퍼센트 기반 프로그레스바를 추가하고, 값이 갱신될 때 막대도 함께 부드럽게 애니메이션 되도록 해야 했다.

## 변경 파일

- `devlog.md`
- `devlog/2026-05-07/039-server-metric-progress-bars.md`
- `src/app/page.servers/view.ts`
- `src/app/page.servers/view.pug`

## 작업 내용

- CPU, Memory, Storage 카드에 각각 프로그레스 트랙과 퍼센트 막대를 추가했다.
- 갱신되는 metric 값을 그대로 쓰되, 프로그레스 폭 계산용 `progressPercent()` helper를 추가해 0~100 범위로 clamp 하도록 정리했다.
- 막대는 `transition-all`, `duration-500`, `ease-out`으로 설정해 자동 갱신 시 숫자와 함께 부드럽게 따라오도록 했다.
- CPU는 sky, Memory는 emerald, Storage는 amber 색상으로 구분했다.

## 검증

- `wiz_project_build(projectName="main", clean=false)`: 통과
- `cd /root/docker-infra/project/main && /opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_wiz_structure_contract`: 통과
- `systemctl restart wiz.docker-infra`: 완료
- `curl http://127.0.0.1:3001/api/system/health`: 서버 기동 확인
- `cd /root/docker-infra/project/main && git diff --check`: 통과
