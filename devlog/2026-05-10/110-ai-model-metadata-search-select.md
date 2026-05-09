# 110. AI 모델 상세 메타데이터와 Search Select 적용

- 날짜: 2026-05-10
- 요청: "모델 정보를 불러올 때 가능하면 모델별로 뭐까지 지원하는지(텍스트, 이미지, 동영상), token 효율? 요금?이 어떻게 되는지도 같이 표시해줘. 그리고 모델 목록 select는 search select 컴포넌트로 바꿔주고"

## 변경 사항

- `src/model/struct/ai_settings.py`
  - OpenAI, Gemini, Ollama 모델 캐시 항목에 `capabilities`, `token_profile`, `efficiency`, `pricing` 메타데이터를 추가했다.
  - OpenAI/Gemini 공식 가격표 링크와 provider별 가격 요약 힌트를 추가했다.
  - Gemini 지원 종료 모델 일부와 OpenAI 기존 지원 종료 상태 표시를 모델 상세 정보에서 같이 활용하도록 정리했다.
  - Gemini 모델 API가 제공하는 입력/출력 토큰 한도를 그대로 저장하고, OpenAI/Ollama는 API가 직접 제공하지 않는 값을 "미제공/공식 문서 확인" 상태로 표시하도록 했다.
- `src/app/page.system/view.ts`
  - 모델 목록을 search select용 item으로 변환하는 helper를 추가했다.
  - 선택한 모델의 지원 범위, 토큰 한도, 효율 추정, 요금 요약, 상태 메시지를 화면에서 표시할 수 있도록 helper를 추가했다.
- `src/app/page.system/view.pug`
  - OpenAI, Gemini, Ollama 모델 선택 UI를 `wiz-component-search-select`로 교체했다.
  - 선택한 모델의 상세 메타데이터와 공식 출처 링크를 provider 카드 안에 표시하도록 추가했다.

## 참고한 공식 출처

- OpenAI Models API: https://developers.openai.com/api/reference/resources/models/methods/list
- OpenAI pricing: https://openai.com/api/pricing/
- Gemini Models API: https://ai.google.dev/api/models
- Gemini pricing: https://ai.google.dev/gemini-api/docs/pricing
- Ollama tags API: https://docs.ollama.com/api/tags

## 검증

- `python -m py_compile project/main/src/model/struct/ai_settings.py` 성공
- `wiz_project_build(projectName="main", clean=false)` 성공
