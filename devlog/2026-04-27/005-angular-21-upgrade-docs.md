# Angular 21 및 WIZ 변경 요약 문서 추가

- **ID**: 005
- **날짜**: 2026-04-27
- **유형**: 문서 업데이트

## 작업 요약
Angular 21 업그레이드 이후 실제로 바뀐 런타임 포인트와 WIZ 객체 동작 변화를 프로젝트 문서로 정리했다.
루트 README에서 바로 접근할 수 있도록 링크를 추가하고, 상세 내용은 별도 문서로 분리했다.

## 변경 파일 목록
### 프로젝트 문서
- `README.md`: 업그레이드 문서 링크 추가
- `docs/angular-21-upgrade.md`: Angular 21, zoneless, `wiz.call`, `wiz.request.query`, signal 예시를 한 문서로 요약

### 작업 기록
- `devlog.md`: 005 항목 추가
- `devlog/2026-04-27/005-angular-21-upgrade-docs.md`: 상세 작업 기록 추가

## 검증
- Markdown 문서 파일 생성 확인
- README 링크 대상 파일 존재 확인
- 문서 내용이 현재 구현 파일(`src/angular/wiz.ts`, `src/controller/base.py`, `src/angular/app/app.module.ts`, `src/app/page.dashboard/view.ts`)과 일치하도록 대조 확인