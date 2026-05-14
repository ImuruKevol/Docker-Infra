# 이미지 관리 Harbor 컴팩트 UI 재구성

- **ID**: 199
- **날짜**: 2026-05-14
- **유형**: 리팩토링

## 작업 요약
이미지 관리 화면의 Harbor 탭을 프로젝트 목록, 선택 프로젝트 요약, 저장소 목록, 태그 목록 중심의 컴팩트 레이아웃으로 재구성했다.
기존 프로젝트 선택, 저장소 선택, 태그 검색, 삭제 플로우는 유지하면서 긴 텍스트와 digest가 레이아웃을 밀지 않도록 표시 방식을 정리했다.

## 원문 요청사항
```text
작업 진행해줘.

기능 자체는 동작하는데, 텍스트들이 잘리고 레이아웃이 난잡해. Harbor 부분의 레이아웃과 디자인을 컴팩트하게 싹 갈아엎어줘. 사용자 플로우 자체는 유지가 되어야 해.
```

## 변경 파일 목록
- `src/app/page.images/view.pug`
  - Harbor 탭을 단일 패널 안의 프로젝트 레일과 상세 영역으로 재배치.
  - 저장소/태그 패널을 컴팩트한 테이블로 정리하고 버튼 줄바꿈, digest 과다 표시, 긴 저장소명 표시 문제를 완화.
- `src/app/page.images/view.ts`
  - 선택 저장소 표시명과 축약 digest 표시용 helper 추가.
- `src/app/page.images/view.scss`
  - 페이지 컴포넌트 host 표시 스타일 추가.
- `devlog.md`
  - 이번 작업 요약 행 추가.
- `devlog/2026-05-14/199-harbor-compact-ui-redesign.md`
  - 작업 상세 기록 추가.

## 검증 결과
- `wiz_project_build(projectName="main", clean=false)` 성공.
