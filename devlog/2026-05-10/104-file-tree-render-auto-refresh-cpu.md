# 104. 파일 트리 렌더 누락과 서버 자원 자동 갱신 지연 개선

## 원본 요청

파일트리가 느려보이는 원인을 찾았어. service.render를 호출하지 않아서 화면이 갱신되지 않는거였어. 자동 갱신은 한 번 호출때마다 2초 가까이 걸리는데, 이 때는 갱신이 되어서 파일 트리도 같이 갱신이 되어서 느려보이는거였어. 일단 이 부분을 개선하고, 자원 자동 갱신이 2초씩이나 걸리는 이유도 분석해서 확실하게 개선해줘.

그리고 추가로 local-master는 cpu가 일정 주기마다 100%를 자꾸 찍고있는데 원인이 뭔지 모르겠어. 원인을 확인해줘

## 변경 파일

- `src/app/component.file.tree/view.ts`
- `src/app/page.servers/view.ts`
- `src/app/page.servers/view.pug`
- `src/app/page.servers/api.py`
- `src/model/struct/local_command_scripts.py`
- `tests/api/test_images_templates_catalog.py`
- `tests/api/test_node_reporter.py`
- `devlog.md`
- `devlog/2026-05-10/104-file-tree-render-auto-refresh-cpu.md`

## 작업 내용

- 파일 트리 컴포넌트에 WIZ `Service`를 주입하고 목록 조회, 파일 열기, 미리보기 닫기, 생성/이름 변경/삭제/이동, 업로드 같은 비동기 상태 변경 후 `service.render()`를 호출하도록 보강했다.
- 서버 상세 자동 갱신이 매번 `refresh_metrics` 실측 API를 직접 호출하지 않도록 변경했다. 이제 UI 자동 갱신은 `cached_detail`만 빠르게 읽고, 실제 수집은 `nodes_monitoring.tick()`이 설정된 주기로 백그라운드에서 실행한다.
- `cached_detail` API가 선택 서버의 백그라운드 수집 tick을 트리거하도록 연결했다. tick은 기존 간격 제한을 그대로 사용하므로 UI polling마다 무거운 수집이 실행되지 않는다.
- `system.metrics` 로컬 명령의 CPU 계산에서 호출 내부 `sleep 1`을 제거했다. `/proc/stat` 이전 샘플을 상태 파일에 저장하고 다음 호출 때 delta로 계산해, 실측 명령 자체가 즉시 반환되도록 했다.
- local-master CPU 스파이크를 확인하기 위해 프로세스 샘플링과 metric history를 확인했다. 높은 CPU 기록은 `metric_refresh` 출처였고, 샘플링 시점의 상위 CPU 프로세스는 `conda shell.* hook`, `kubectl completion zsh`, Codex/VS Code/WIZ 서버 프로세스였다. 서비스 컨테이너보다는 로컬 개발 환경과 기존 잦은 실측 방식이 피크를 차트에 노출한 것으로 판단했다.

## 검증 결과

- `python -m py_compile src/model/struct/local_command_scripts.py src/app/page.servers/api.py` 통과
- `python -m unittest tests.api.test_node_reporter.NodeReporterStaticContractTest tests.api.test_images_templates_catalog.ImagesTemplatesStaticContractTest` 통과
- `system.metrics` 스크립트는 1초 간격 샘플 후 실제 실행 시간이 약 `0.03s`로 확인됨
- `wiz_project_build(projectName="main", clean=false)` 성공
- `git diff --check` 통과
