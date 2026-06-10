# 서비스 생성 템플릿 변수와 배포 진행 표시 보강

## 원 요청

- 리뷰 ID: `gclfqfajlpzebygbzttotskbqxowvtjv`
- 제목: 서비스 생성 로직 개선
- 요청 내용: 템플릿 변수 중 이미지/포트 항목은 화면에서 숨기고, secret 변수는 기본 표시 시 자동 생성값을 보여주며, 서비스 생성 시 compose 공개 포트와 nginx 대상 서버 IP가 올바르게 저장되도록 보완. 생성 직후 이미지 pull 중이면 상세 화면에서 진행 상황을 표시하도록 개선.

## 변경 파일

- `src/app/page.services.create/view.ts`
- `src/app/page.services.create/view.pug`
- `src/model/struct/services_detail_fast.py`
- `src/model/struct/services_ports.py`
- `src/model/struct/services_deploy.py`
- `tests/api/test_services_preflight.py`
- `devlog.md`
- `devlog/2026-06-10/021-service-create-template-deploy-flow.md`

## 작업 내용

- 서비스 생성 템플릿 필드에서 이미지/포트 계열 변수는 관리 대상 필드로 분류해 입력 폼에서 제외했다.
- secret 템플릿 변수는 비어 있거나 placeholder 값이면 화면 로드 시 40자 임의 값으로 생성하고 기본 표시 상태로 열리도록 했다.
- 서비스 생성 버튼이 저장 후 즉시 백그라운드 배포를 시작하고, 생성된 서비스 상세 화면으로 이동하도록 연결했다.
- 배포 중 공개 포트 재할당을 로컬 기준이 아니라 선택된 배포 노드 기준으로 확인하도록 원격 SSH 포트 점검을 추가했다.
- 상세 화면 경량 overview 응답에 최근 service operation을 포함해 생성 직후 이미지 pull/stack deploy 진행 배너가 유지되도록 했다.
- 정적 계약 테스트를 현재 템플릿 전용 생성 화면과 배포 진행 흐름에 맞게 보강했다.

## 검증

- `python -m unittest tests/api/test_services_preflight.py` 통과
- WIZ project build `main` 통과
- `python -m py_compile src/model/struct/services_detail_fast.py src/model/struct/services_ports.py src/model/struct/services_deploy.py tests/api/test_services_preflight.py` 통과

## 남은 확인

- 실제 mini3 서버에 새 서비스를 생성하는 실환경 배포 검증은 수행하지 않았다. 원격 SSH 포트 점검 실패 시 배포를 중단하는 정책은 후속 024 항목에서 보강했다.
