# 162. 시스템 설정 AI 탭 서브탭화와 모델 표시 순서 옵션 추가

## 사용자 요청

- 리뷰 ID: `yaoxunfdtjurlvgdfosxmlhjfonhxnsy`
- 요청: "작업을 진행해줘. 일반 사용자가 아무것도 몰라도 사용할 수 있도록 UI/UX를 신경쓰는거 잊지 마."
- 리뷰어 요청 내용: 시스템 설정의 AI 탭에서 Codex, GPT, Gemini, Ollama, 등록 노드 Ollama 설정이 한 화면에 길게 보여 번잡하므로 AI 탭 내부를 서브탭 형식으로 바꾸고, 사용 체크를 해야 설정 항목이 보이도록 수정. 모델 리스팅 순서도 설정 가능하게 개선.

## 변경 파일

- `src/app/page.system/view.pug`
  - AI 탭 내부에 Codex, OpenAI GPT, Gemini, Ollama, 등록 노드 Ollama 서브탭을 추가.
  - 각 서브탭 상단에 사용 체크를 배치하고, 비활성 상태에서는 상세 설정을 숨김.
  - 비활성 상태에서도 사용 상태를 저장할 수 있도록 상태 저장 버튼을 제공.
  - OpenAI/Gemini/Ollama/등록 노드 Ollama 설정에 모델 표시 순서 선택 UI를 추가.
- `src/app/page.system/view.ts`
  - AI 서브탭 상태, 섹션 활성화 토글, 사용 중 카운트, 서브탭 요약 표시 로직을 추가.
  - 모델 목록 표시 순서를 모델명 A-Z, 모델명 Z-A, 최근 생성/수정순, 오래된 생성/수정순, 권장 상태 우선으로 정렬할 수 있게 처리.
  - 등록 노드 Ollama 모델 선택 목록도 동일 정렬 설정을 적용하도록 변경.
- `src/model/struct/ai_settings.py`
  - `model_sort` 설정 기본값과 정규화 로직을 OpenAI/Gemini/Ollama/등록 노드 런타임 설정에 추가.

## 확인 결과

- `wiz_project_build(projectName="main", clean=false)` 실행 성공.
- Angular/Pug 빌드가 완료되어 `/root/docker-infra/project/main/build/dist/build` 산출물이 생성됨.

## 남은 리스크

- 실제 브라우저 화면에서 클릭/저장 흐름까지 수동 검증하지는 못함.
- 모델 API 목록 자체는 기존 캐시/조회 결과를 프론트에서 정렬하므로, 외부 연동 실패 상태에서는 정렬 가능한 모델 목록이 없을 수 있음.
