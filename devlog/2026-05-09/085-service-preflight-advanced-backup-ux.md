# 085. 서비스 preflight 원격 점검과 상세 고급/백업 UX 후속 보강

## 사용자 요청

> 이어서 진행해줘

이전 요청에서 작성한 서비스 관리 UX/자동화 검수 TODO를 이어서 진행했다. 특히 실제 배포 대상 기준 자동 점검, 서비스 상세의 위험한 고급 편집 격리, 백업/스냅샷/복원 문구 정리를 우선 처리했다.

## 변경 파일

- `src/model/struct/services_preflight.py`
- `src/model/struct/services_deploy.py`
- `src/model/struct/services_wizard.py`
- `src/app/page.services.create/view.ts`
- `src/app/page.services.create/view.pug`
- `src/app/page.services/view.ts`
- `src/app/page.services/view.pug`
- `docs/service-management-audit-todo.md`
- `docs/docker-infra-development-todo.md`
- `docs/docker-infra-remaining-todo.md`
- `tests/api/test_services_preflight.py`

## 변경 내용

- 서비스 생성 preflight에 등록 서버 후보 확인, 원격 Docker image inspect, 원격 포트 사용 여부 확인을 추가했다.
- 이미지 확인 결과를 로컬 이미지, Docker Hub pull 가능성, 외부 registry 경고로 나눠 사용자용 메시지로 표시하도록 정리했다.
- 배포 중 자동 조정된 published port와 domain port mapping 결과를 최신 compose version metadata와 service metadata에 기록하도록 했다.
- 템플릿에서 자동 생성된 secret은 값이 아니라 key 목록만 wizard/source metadata에 남겨 추후 마스킹/재생성 UI가 확장 가능하도록 했다.
- `/services/create` preflight 카드와 실패 메시지에 원인/조치 문구를 추가했다.
- 서비스 상세의 nginx 원문 편집은 확인 모달을 통과해야 열리도록 분리하고, 기술 정보 영역은 기본적으로 읽기 중심으로 정리했다.
- 컨테이너 raw ID는 기본 노출하지 않고 접힌 내부 정보로 축소했다.
- 이미지 백업/현재 상태 백업/복원 문구에 서비스 영향, 일시 정지 가능성, 복원 후 적용 필요성을 명확히 표시했다.
- 서비스 관리 검수 TODO와 남은 TODO 문서에 완료 항목을 반영했다.

## 검증

- `/opt/conda/envs/docker-infra/bin/python -m py_compile project/main/src/model/struct/services_preflight.py project/main/src/model/struct/services_deploy.py project/main/src/model/struct/services_wizard.py project/main/src/model/struct/services.py project/main/src/app/page.services.create/api.py project/main/src/app/page.services/api.py`
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_services_preflight.ServicesPreflightStaticContractTest tests.api.test_images_templates_catalog.ImagesTemplatesStaticContractTest`
- `wiz_project_build(projectName="main", clean=false)`

모두 통과했다.
