# 071. 서비스 생성 단계 단순화와 서비스 목록·상세 UX 재설계 TODO 반영

## 사용자 요청

고급 설정은 별도 단계로 빼지 말고 2단계에 토글로 추가한다. 도메인 단계에서는 앞 주소 input이 도메인보다 앞에 와야 하고, 접속 대상이라는 표현 대신 연결 포트로 표현한다. 포트 선택은 select가 아니라 버튼형 radio group 디자인으로 바꾼다. 서비스 목록과 상세 화면은 개발자스럽지 않게, 새 서비스 생성과 비슷하게 비전문 관리자도 사용할 수 있는 수준으로 재설계해야 하며 이 내용을 TODO 문서에 반영한다.

## 변경 사항

- `/services/create` 생성 wizard를 5단계에서 4단계로 줄였다.
- 환경변수와 데이터 보관 설정을 별도 3단계에서 제거하고 2단계의 고급 설정 토글 안으로 이동했다.
- 도메인 단계를 3단계로 당기고, 도메인 입력 순서를 앞 주소 다음 도메인 선택 순서로 정리했다.
- 도메인 연결 대상 표현을 `연결 포트`로 변경했다.
- 연결 포트 선택 UI를 select에서 버튼형 radio group으로 변경했다.
- 서비스 ID라는 표현이 생성 화면에 다시 노출되지 않도록 자동 처리 안내 문구를 내부 식별값 중심으로 수정했다.
- 전체 TODO에 서비스 목록/상세 화면을 운영자용 상태·접속 주소·간단 액션 중심으로 재설계하는 5.5 섹션을 추가했다.
- 남은 TODO에 서비스 목록/상세 UX 재설계 체크리스트를 추가하고, 서비스 생성 wizard의 오래된 신규 도메인/별도 고급 단계/서버 선택 표현을 정리했다.

## 변경 파일

- `devlog.md`
- `devlog/2026-05-09/071-service-create-flow-and-service-ux-todo.md`
- `docs/docker-infra-development-todo.md`
- `docs/docker-infra-remaining-todo.md`
- `src/app/page.services.create/view.pug`
- `src/app/page.services.create/view.ts`

## 검증

- `wiz_project_build(clean=false, projectName="main")`
- `git diff --check`
