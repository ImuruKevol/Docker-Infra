# 컨테이너 내부 파일 탭 실행 중 컨테이너만 표시

- 날짜: 2026-06-10
- 리뷰 ID: qklfbvdopgfyvgupflfuolyislfknevd
- 요청자: 권태욱

## 사용자 원문

컨테이너 내부 파일의 컨테이너 목록에 중지된 컨테이너는 어차피 확인이 안되니까 목록에 표시하지 말아줘.

## 변경 파일

- `src/app/page.services/view.ts`
- `devlog.md`
- `devlog/2026-06-10/018-container-file-running-only.md`

## 작업 내용

- 컨테이너 파일 탭의 컨테이너 목록 필터를 `id`, `node_id` 존재 여부만 보던 방식에서 실행 가능한 상태만 포함하도록 변경했다.
- `containerSignal()` 기준으로 `running`, `healthy`, `unhealthy`, `starting` 상태만 컨테이너 내부 파일 목록에 표시되게 했다.

## 확인 결과

- `wiz_project_build(projectName="main", clean=false)` 성공.
- Playwright로 `https://infra-dev.nanoha.kr/access` 로그인 후 `season-wiz-project=main`, `season-wiz-devmode=true` 쿠키를 넣고 서비스 상세 화면을 확인했다.
- 컨테이너 파일 탭에서 표시된 컨테이너 목록에 `중지됨`, `생성됨`, `일시정지`, `재시작 중` 라벨이 없고 실행 중 컨테이너만 표시되는 것을 확인했다.

## 남은 리스크

- 검증 대상 서비스에는 실제 중지 컨테이너가 섞여 있지 않아, 혼합 상태 서비스에서의 시각 검증은 수행하지 못했다.
