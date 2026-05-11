# 130. AI 서비스 초안 이미지 이름과 버전 검증 보강

## 요청

- 원 요청: "작업 지시서를 참고해서 버그를 수정해줘."
- 리뷰 ID: `xtcbgryxpepnvqtdzhdyttxeyboggbcp`
- 리뷰 내용: AI를 이용해 서비스 초안을 생성할 때 이미지 및 이미지 버전 확인 로직이 빠져 있으므로, 초안 생성 후 validation 체크에서 이미지와 이미지 버전도 확인하도록 수정.

## 변경 파일

- `src/model/struct/ai_assistant.py`
- `devlog.md`
- `devlog/2026-05-11/130-ai-service-draft-image-version-validation.md`

## 작업 내용

- AI 서비스 초안 검증 단계에서 컴포넌트의 이미지 이름 누락을 먼저 검출하도록 추가했다.
- Compose 검증 후 정규화된 각 서비스의 `image` 참조를 `services_wizard.check_image()`로 확인하고, 이미지 이름 또는 태그/다이제스트를 찾지 못하면 AI output 검증 실패로 처리하도록 했다.
- 이미지 검증 실패가 기존 AI 자동 보정 루프에 전달되도록 `AI_OUTPUT_IMAGE_VALIDATION_FAILED` 세부 오류를 구성했다.
- AI 프롬프트와 서비스 생성 컨텍스트에 이미지 이름 및 태그/다이제스트 검증 기대사항을 추가했다.

## 확인

- `python -m py_compile project/main/src/model/struct/ai_assistant.py` 성공
- WIZ `wiz_project_build(projectName="main", clean=false)` 성공

## 남은 리스크

- 외부/private registry 이미지는 기존 `check_image()` 정책과 동일하게 배포 중 확인 대상으로 남는다.
