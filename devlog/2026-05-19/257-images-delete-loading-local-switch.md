# 이미지 삭제 진행 표시와 로컬 서버 전환 로딩 개선

- **ID**: 257
- **날짜**: 2026-05-19
- **유형**: UX 개선

## 작업 요약
이미지 관리 화면의 삭제 작업에 진행 중 배너와 indeterminate progress bar를 추가해 작업 대기 상태를 즉시 보여주도록 수정했다.
로컬 저장소에서 서버를 바꿀 때 이전 서버의 이미지 목록과 상세 내용을 즉시 비우고, 새 서버 조회가 끝날 때까지 로딩 상태만 표시하도록 보강했다.

## 원문 요청사항
```text
작업 진행해줘.

이미지 관리 화면에서 이미지 삭제 시 로딩 화면 없이 그냥 기다리다가 삭제했다는 모달이 뜨고 있어.
이렇게 하면 너무 UI/UX적으로 좋지 않아. 삭제 상태에 대해 로딩을 보여주던가, 아니면 progress 바같은걸 보여주던가 해줘.
그리고 로컬 저장소 탭에서 각 서버 선택 시 그냥 헤더 부분의 라벨만 바뀌고 아래 컨텐츠가 바뀌는건 한참 나중이야. 근데 이러니까 오작동할 위험이 너무 커. 다른 서버를 선택하면 일단 목록 및 컨텐츠를 한 번 싹 날리고 로드 중 표시를 띄웠다가 로드 되면 표시하도록 수정해줘.
```

## 변경 파일 목록
- `src/app/page.images/view.ts`
  - 삭제/정리 작업용 진행 상태 signal과 진행 배너 상태 헬퍼를 추가했다.
  - Harbor/로컬 이미지 삭제, 프로젝트/저장소 삭제, 미사용 이미지 정리 실행 전에 화면을 즉시 렌더링해 진행 상태가 보이도록 수정했다.
  - 로컬 서버 상세 조회 시 요청 ID를 사용해 오래된 응답 반영을 막고, 서버 전환 시 기존 상세/목록을 즉시 초기화하도록 수정했다.
- `src/app/page.images/view.pug`
  - 이미지 삭제/정리 진행 배너와 progress bar를 추가했다.
  - 로컬 저장소 서버 선택 시 목록 초기화 후 로드 중 표시와 조회 오류 표시를 추가했다.
- `src/app/page.images/view.scss`
  - 진행 상태용 indeterminate progress bar 애니메이션과 reduced-motion 처리를 추가했다.

## 검증 결과
- `wiz_project_build(clean=false)` 성공.
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_images_templates_catalog` 성공 (`OK`, 2건 skip).
- Playwright에서 `season-wiz-project=main`, `season-wiz-devmode=true` 쿠키를 추가해 `/images` 접근을 확인했으나 인증 세션이 없어 `/access`로 리다이렉트됨.
