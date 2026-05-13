# 매크로 스크립트 CRLF 줄바꿈 정규화

- **ID**: 151
- **날짜**: 2026-05-12
- **유형**: 버그 수정

## 작업 요약
CRLF로 저장된 매크로 스크립트가 실행 중 `$'\r'` 명령어 오류를 stderr에 남기는 문제를 수정했다.
저장 시점과 실행 시점 모두에서 스크립트 줄바꿈을 LF로 정규화해, 기존에 CRLF로 저장된 매크로도 재저장 없이 정상 실행되도록 했다.

## 원문 요청사항
```text
# ReviewOps Codex 작업 요청

아래 요청을 현재 프로젝트 루트에서 처리하세요. 필요한 파일을 직접 수정하고, 마지막 응답은 한국어로 간결하게 작성하세요.
스트리밍 응답은 사용하지 않습니다. 작업이 끝난 뒤 변경 요약, 확인한 내용, 남은 리스크만 정리하세요.
이 작업의 세션 단위는 아래 리뷰 ID입니다. 리뷰 ID가 같으면 같은 Codex 히스토리 맥락으로 이어서 처리하세요.

## 사용자 요청

실행은 잘 되는데 매크로 실행 시 아래 에러 메세지가 중간에 있어. 근데 스크립트는 잘 돌아가.
[stderr] /tmp/docker-infra-macro.G3fLed.sh: 줄 2: $'\r': 명령어를 찾을 수 없음

## 리뷰 요약

- 리뷰 ID: fdbwtzahvpcbkpgpxbajrhdbscykwudy
- 제목: 매크로 기능 추가
- 요청 링크: https://infra-dev.nanoha.kr/macros
- Codex 요청자: 권태욱
- 프로젝트 루트: /root/docker-infra
- Codex 세션 ID: 019e1c4d-f255-7d41-8350-051399e563c8
- 스크린샷 컨텍스트: 없음
- 에이전트 작업 지시서 컨텍스트: 없음
- HTML 문서 생성 규칙 컨텍스트: 없음
- HTML 문서 설정 컨텍스트: 없음
- HTML 프로젝트 인스트럭션 파일: 없음
- 첨부파일 컨텍스트: 0개

## 세션 처리

저장된 Codex 세션을 resume해 이전 대화 맥락을 우선 사용하세요. 이전 Codex 히스토리는 이 요청에 포함되지 않습니다.
```

## 변경 파일 목록
- `src/model/struct/macros_shared.py`
- `src/model/struct/macros_store.py`
- `src/model/struct/macros_runner.py`
- `tests/api/test_server_macros.py`
- `devlog.md`
- `devlog/2026-05-12/151-macro-script-crlf-normalization.md`

## 검증 결과
- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/macros_shared.py src/model/struct/macros_store.py src/model/struct/macros_runner.py tests/api/test_server_macros.py` 성공
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_server_macros.ServerMacrosStaticContractTest` 성공
- 직접 helper 검증으로 CRLF 입력이 LF로 변환되는 것 확인

## 남은 리스크
기존 실행 로그에 이미 기록된 `$'\r'` stderr 라인은 소급 삭제하지 않았다.
