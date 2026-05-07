# 시스템 설정 인증서 UUID fallback, 파일 경로 선택 parent fallback, 파일 트리 모달 스크롤 제한 적용

- **ID**: 050
- **날짜**: 2026-05-07
- **유형**: 버그 수정

## 작업 요약
시스템 설정의 SSL 인증서 추가 모달에서 `crypto.randomUUID` 미지원 브라우저 예외를 fallback ID 생성으로 대체했다.  
웹서버 설정 경로 선택 모달은 파일 경로를 디렉토리로 열던 문제를 수정해, 파일 경로가 들어오면 부모 디렉토리를 열도록 정리했다.  
파일 목록이 많을 때 모달 높이를 넘기던 문제도 스크롤 영역 제한으로 함께 수정했다.

## 원문 요청사항
```text
ssl 인증서 경로 추가에서는 crypto.randomUUID is not a function 이런 에러가 떠.
그리고 nginx 설정 경로 선택에 대한 파일 트리 모달은 파일을 디렉토리로 열려고 해서 "선택한 경로를 열 수 없습니다." 이런 에러가 떠. 바로 파일 부분을 지우고 디렉토리를 지정하면 정상적으로 목록이 표시되고 있어. 근데 파일트리 컴포넌트에서 파일 목록이 많으면 모달이 화면을 초과하고 있어. 파일 목록은 max height 지정이 필요할 것 같아.
```

## 변경 파일 목록
- `src/app/page.system/view.ts`
  - SSL 인증서 draft 저장 시 `crypto.randomUUID()` 직접 호출을 제거했다.
  - 브라우저가 `randomUUID`를 지원하지 않아도 동작하도록 로컬 fallback ID 생성 helper를 추가했다.
- `src/app/page.system/api.py`
  - `browse_local_files()`가 파일 경로를 받으면 404를 내지 않고 부모 디렉토리를 열도록 수정했다.
- `src/app/page.system/view.pug`
  - 경로 선택 모달 전체 높이를 viewport 안으로 제한했다.
  - 파일 목록 영역에 `max-height`와 내부 스크롤을 추가했다.
- `tests/api/test_system_settings_dynamic_menu.py`
  - `browse_local_files()`가 파일 경로를 받아도 부모 디렉토리를 정상적으로 반환하는 live 검증을 추가했다.

## 검증 결과
- `wiz_project_build(projectName="main", clean=false)` 통과
- `systemctl restart wiz.docker-infra` 후 서비스 `active` 확인
- `python -m unittest tests.api.test_system_settings_dynamic_menu tests.api.test_wiz_structure_contract` 통과 (`skipped=3`)
- `git diff --check` 통과
- live 확인
  - `/wiz/api/page.system/browse_local_files`에 `src/app/page.system/view.ts` 파일 경로를 넘겼을 때 `200` 응답 확인
  - 응답 `data.path`가 `/root/docker-infra/project/main/src/app/page.system` 부모 디렉토리로 내려오는 것 확인
  - 반환 목록에 `view.ts`가 포함되는 것 확인

## 비고
- 이번 수정은 `page.system` app API 변경이 포함되어 있어 `wiz.docker-infra` 데몬을 1회 재시작했다.
