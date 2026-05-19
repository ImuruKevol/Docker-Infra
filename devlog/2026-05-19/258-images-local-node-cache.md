# 이미지 관리 로컬 저장소 서버별 화면 캐시 추가

- **ID**: 258
- **날짜**: 2026-05-19
- **유형**: UX 개선

## 작업 요약
이미지 관리 화면의 로컬 저장소 탭에서 한 번 조회한 서버별 이미지 상세를 화면 인스턴스 안에 캐시하도록 수정했다.
서버를 다시 선택하면 API를 재호출하지 않고 캐시된 목록과 요약을 즉시 표시하며, 삭제/정리/업로드 후에는 해당 서버 캐시를 최신 응답으로 갱신한다.

## 원문 요청사항
```text
같은 화면 내에서 캐싱 처리는 해야해. 지금은 서버를 왔다갔다 할 때 그때마다 계속 이미지 목록을 다시 불러오고 있는데, 캐싱처리해줘.
```

## 변경 파일 목록
- `src/app/page.images/view.ts`
  - 로컬 저장소 서버별 상세 응답을 `localDetailCache`에 저장하고 재선택 시 캐시를 우선 사용하도록 수정했다.
  - 전체 새로고침 시 캐시와 진행 중 로컬 조회 요청을 무효화하도록 보강했다.
  - 로컬 이미지 업로드, 삭제, 미사용 이미지 정리 결과가 선택 서버의 캐시와 요약에 반영되도록 정리했다.
  - 서버 전환 중 이전 조회 응답은 UI에 반영하지 않고 캐시만 갱신하도록 유지했다.

## 검증 결과
- `wiz_project_build(clean=false)` 성공.
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_images_templates_catalog` 성공 (`OK`, 2건 skip).
- `git diff --check` 통과.
- Playwright에서 `season-wiz-project=main`, `season-wiz-devmode=true` 쿠키를 추가해 `/images` 접근을 확인했으나 인증 세션이 없어 `/access`로 리다이렉트됨.
