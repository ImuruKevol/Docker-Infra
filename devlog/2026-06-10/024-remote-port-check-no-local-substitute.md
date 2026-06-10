# 원격 포트 점검 실패 시 로컬 대체 확인 제거

## 원 요청

- 리뷰 ID: `gclfqfajlpzebygbzttotskbqxowvtjv`
- 제목: 서비스 생성 로직 개선
- 요청 내용: 원격 SSH 포트 점검이 실패했을 때 로컬 포트 확인으로 대체하면 안 되며, 이런 배포 경로에서 대체 확인을 사용하지 않도록 수정.

## 변경 파일

- `src/model/struct/services_ports.py`
- `src/model/struct/services_deploy.py`
- `tests/api/test_services_preflight.py`
- `devlog.md`
- `devlog/2026-06-10/021-service-create-template-deploy-flow.md`
- `devlog/2026-06-10/024-remote-port-check-no-local-substitute.md`

## 작업 내용

- 원격 배포 노드의 SSH 포트 점검 실패, 노드 상세 조회 실패, 해석 불가능한 출력은 `PortCheckError`로 즉시 전파하도록 변경했다.
- 원격 노드 포트 점검 실패 시 로컬 포트 확인을 사용하던 분기를 제거했다.
- 문자열 포트 처리에서 포트 점검 오류를 삼키고 원본 포트를 유지하던 경로를 제거했다.
- 배포 대상 노드가 없거나 원격 포트 점검이 실패하면 operation을 실패 상태로 전환하고 배포를 중단하도록 했다.
- 정적 계약 테스트에 원격 점검 실패 시 로컬 확인 분기가 다시 들어오지 않도록 검증을 추가했다.

## 검증

- `python -m unittest tests/api/test_services_preflight.py` 통과
- `python -m py_compile src/model/struct/services_ports.py src/model/struct/services_deploy.py tests/api/test_services_preflight.py` 통과
- WIZ project build `main` 통과

## 남은 확인

- 실제 mini3 서버에 새 서비스를 생성하는 실환경 배포 검증은 수행하지 않았다.
