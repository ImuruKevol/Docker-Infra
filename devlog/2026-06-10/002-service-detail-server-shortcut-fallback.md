# 서비스 상세 서버 바로가기 배치 서버 fallback 보강

## 사용자 요청

작업 시작

리뷰 ID: `kpptiqrbwldmfctupqrlgiiluavtrfat`

리뷰 내용:
- 서비스 상세 화면에서 서버 바로가기 버튼이 있는데, 서비스 컨테이너들이 정상적으로 뜨기 전에는 표시가 안되는 것 같아 확인해달라는 요청.

## 변경 파일

- `src/app/page.services/view.ts`
  - 서버 바로가기 대상 계산 시 런타임 컨테이너/도메인/태스크에서 서버 ID를 찾지 못하면 서비스의 `target_node_policy` 또는 `metadata.placement`에 저장된 배치 서버 ID를 fallback으로 사용하도록 보강했다.
  - 배치 서버 라벨은 등록 서버 목록, 자동 배치 추천 정보, 마이그레이션 메타데이터 순서로 보정하고 마지막에는 서버 ID를 표시하도록 했다.
  - 서비스 상세 선택 시 서버 목록을 조용히 미리 불러와 fallback 라벨을 실제 서버명으로 갱신할 수 있게 했다.

## 확인 결과

- `wiz_project_build(projectName=main, clean=false)` 통과.
- `curl -I`에 `season-wiz-project=main`, `season-wiz-devmode=true` 쿠키를 추가해 `https://infra-dev.nanoha.kr/dashboard` 응답이 `200 OK`임을 확인했다.
