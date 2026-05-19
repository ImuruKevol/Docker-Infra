# 251 서비스 관리 상태 표시와 적용 버튼 문구 정리

## 요청

현재 wiki_service가 도메인으로 접속은 잘 되고 있어. 근데 서비스 관리 화면에서는 상태가 준비 중이라고 뜨고 있는데, 이게 왜 뜨는건지 모르겠어. 상태값의 기준이 너무 모호해. 준비 중인 서비스의 경우엔 "다시 적용"이 아니라 "서비스 적용"이라고 뜨는데, 이것도 그냥 마찬가지로 삭제하면 될 것 같아.

## 변경 내용

- 서비스 목록과 상세 헤더에서 DB lifecycle 기반 상태 배지를 제거했다.
- 상세 상단 요약의 "현재 상태"를 "실행 기준"으로 바꾸고, 컨테이너 런타임/도메인 연결/최근 작업 기준 문구로 표시하도록 정리했다.
- 상단 적용 버튼 문구를 상태값과 무관하게 항상 "다시 적용"으로 고정했다.
- 서비스 관리 화면의 draft 표시 문구를 "저장됨"으로 바꾸고, 배포 작업 로그 라벨은 "설정 적용"으로 정리했다.
- 수정/이미지 복원 안내에서 "준비 중"과 "서비스 적용" 기준 안내를 제거했다.
- 서비스 관리 화면에 모호한 lifecycle 상태 문구가 다시 노출되지 않도록 정적 계약 테스트를 추가했다.

## 변경 파일

- `src/app/page.services/view.pug`
- `src/app/page.services/view.ts`
- `tests/api/test_services_preflight.py`
- `devlog.md`
- `devlog/2026-05-19/251-service-management-status-label-cleanup.md`

## 검증

- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_services_preflight` 통과
- WIZ `main` 프로젝트 빌드 통과

## 남은 리스크

- 브라우저 실화면 검증은 별도로 수행하지 않았다.
- 작업 전부터 같은 프로젝트에 다른 미커밋 변경과 미추적 devlog가 있었으며, 이번 작업은 필요한 파일만 수정하고 기존 변경은 되돌리지 않았다.
