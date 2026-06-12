# 서비스 상세 Compose/Nginx 탭 제거

## 요청

- 리뷰 ID: `rwckyzwrnxhehtpkgyujeowghxhklfjx`
- 제목: 서비스 관리 화면 상세 수정
- 원 요청: "서비스 관리 상세에 Compose/Nginx 탭 제거해줘. 그냥 제거하면 돼. 어차피 수정할게 있으면 agent로 하거나 하면 돼."

## 변경 사항

- 서비스 상세 탭 목록에서 `Compose/Nginx` 탭 항목을 제거했다.
- 상세 탭 라우팅 허용 키에서 `source`를 제외해 `/services/{id}/source` 직접 접근 시 기본 `overview` 탭으로 정규화되도록 했다.
- 정적 계약 테스트의 기대값을 `Compose/Nginx` 라벨 비노출 기준으로 갱신했다.

## 변경 파일

- `src/app/page.services/view.ts`
- `tests/api/test_services_preflight.py`
- `devlog.md`
- `devlog/2026-06-11/012-service-detail-compose-nginx-tab-removal.md`

## 검증

- 성공: `wiz_project_build(projectName="main", clean=false)`
- 성공: `python -m unittest tests.api.test_services_preflight.ServicesPreflightStaticContractTest.test_service_detail_operator_runtime_summary_is_wired tests.api.test_services_preflight.ServicesPreflightStaticContractTest.test_p7_nginx_and_domain_certificate_contract_is_wired -q`
- 성공: `rg -n "Compose/Nginx" src/app/page.services/view.ts build/dist/build` 결과 없음.
- 성공: `season-wiz-project=main; season-wiz-devmode=true` 쿠키로 `http://127.0.0.1:3001/services/65f94590-edba-4279-9aec-5c481ac05439/source` HEAD 요청 200 확인.
- 참고: `python -m unittest tests.api.test_services_preflight -q` 전체 실행은 기존 `page.services.create` 템플릿 변수 문구 기대값 불일치로 실패했다. 이번 변경과 닿는 두 테스트는 별도 통과했다.
