# 283. 서비스 생성 방식 선택 UX와 중복 입력 노출 정리

## 요청

> 현재 템플릿 생성 시 화면의 느낌이 딱 적당해. 참고해서 진행해줘.
>
> 서비스 생성 화면에서 템플릿을 적용할 수 있는 카드가 있는데, UX를 아예 고려하지 않고 추가가 되었어. 템플릿 기반/AI 자동 구성/직접 작성 이렇게 선택할 수 있도록 하고, 선택 여부에 따라 각 필요한 UI/UX를 구성하도록 해야해. 그리고 서비스 이름 등 내용이 중복해서 화면에 들어가있는 문제도 있어.

## 변경 파일

- `src/app/page.services.create/view.ts`
- `src/app/page.services.create/view.pug`
- `tests/api/test_services_preflight.py`
- `devlog.md`
- `devlog/2026-05-20/283-service-create-mode-selector.md`

## 변경 내용

- 서비스 생성 1단계에 `템플릿 기반`, `AI 자동 구성`, `직접 작성` 선택 카드를 추가했다.
- 선택한 생성 방식의 입력 패널만 표시되도록 템플릿, AI, Compose 직접 작성 영역을 분리했다.
- 템플릿 작성 화면의 색감과 카드 밀도는 유지하면서, AI와 직접 작성 영역은 선택 시에만 노출되도록 정리했다.
- 서비스 이름 입력이 템플릿/AI 영역에 동시에 보이던 문제를 선택 방식별 단일 노출 구조로 줄였다.
- 템플릿/AI 사용 불가 상태에 따라 기본 생성 방식을 자동 보정하고, 서버 Compose 가져오기 흐름은 직접 작성 모드로 전환되도록 했다.
- 서비스 생성 화면 정적 계약 테스트를 생성 방식 선택 UI 기준으로 갱신했다.

## 확인

- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_services_preflight.ServicesPreflightStaticContractTest`
- `wiz_project_build(projectName="main", clean=false)` 성공
- `season-wiz-project=main`, `season-wiz-devmode=true` 쿠키를 넣고 `https://infra-dev.nanoha.kr/services/create` HEAD 요청 200 확인
- 같은 쿠키로 `https://infra-dev.nanoha.kr/wiz/api/page.services.create/load` POST 요청 시 인증 쿠키가 없어 401 `AUTHENTICATION_REQUIRED` 응답 확인

## 남은 리스크

- 로그인 세션 쿠키가 없어 실제 인증 후 브라우저 화면에서 생성 방식 전환과 템플릿 적용 흐름은 직접 확인하지 못했다.
