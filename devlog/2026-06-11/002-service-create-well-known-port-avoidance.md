# 002 서비스 생성 공개 포트 well-known 자동 할당 회피

- 날짜: 2026-06-11
- 리뷰 ID: lizneczxflvmiljgjvuorrtqfctqjdyi

## 사용자 원 요청

- 서비스 생성 시 외부로 오픈되는 포트는 해당 서버의 사용 중인 포트를 조회하여 자동으로 수정되고 있음.
- 이 때 0 ~ 1023번 포트는 잘 알려진 포트이므로 자동으로 사용하게 하면 안됨.
- 예를 들어 컨테이너 ssh 서비스가 22번 포트를 사용하더라도 외부 22번으로 그대로 매핑하지 말고, 왠만하면 49152 ~ 65535 범위의 동적 사설 포트를 사용하도록 할 것.

## 변경 파일

- `src/model/struct/services_ports.py`
- `src/model/struct/services_preflight.py`
- `tests/api/test_services_preflight.py`
- `devlog.md`
- `devlog/2026-06-11/002-service-create-well-known-port-avoidance.md`

## 변경 내용

- 공개 포트 자동 할당 시 0~1023 well-known 포트 요청은 49152~65535 동적 사설 포트 범위를 먼저 탐색하도록 변경했다.
- 동적 사설 포트 범위가 모두 불가한 경우에도 1024 이상만 후보로 사용해 well-known 포트가 자동 선택되지 않도록 했다.
- well-known 포트로 인해 조정된 allocation에는 `well_known_reserved` 사유를 남기도록 했다.
- 사전점검 메시지를 "사용 중"뿐 아니라 정책상 자동 사용을 피해야 하는 포트도 포함하는 표현으로 보정했다.
- 22, 80, 443 published 포트가 각각 49152, 49153, 49154로 조정되는 단위 테스트를 추가했다.

## 검증 결과

- 성공: `python -m unittest project/main/tests/api/test_services_preflight.py -k service_port_allocation`
- 성공: `python -m py_compile project/main/src/model/struct/services_ports.py project/main/src/model/struct/services_preflight.py project/main/tests/api/test_services_preflight.py`
- 성공: `python -m unittest project/main/tests/api/test_services_preflight.py`
- 성공: WIZ project build `main`
