# 014 Storage bootstrap 카드 서버 목록 압축과 불필요한 설명 제거

## 요청

- Review ID: `zyqsvvysbltycxwkhsghunmhrnxytqqu`
- 제목: 스토리지 화면 개선

```text
"Ceph OSD slot 후보이며 CephFS bind mount 대상입니다." 같은 불필요한 텍스트들도 전부 삭제하고 서버가 몇 개가 올지 모르니 확실하게 좀 요약해서 Dockerized Ceph cluster bootstrap 카드를 컴팩트하게 수정해줘.
```

## 변경 파일

- `src/app/page.storage/view.pug`
  - bootstrap 카드의 설명 문단과 서버별 storage note 표시를 제거했다.
  - 서버 수, OSD 가능 수, 최근 operation 상태를 제목 옆 요약 배지로 압축했다.
  - 서버 목록을 카드 그리드에서 최대 높이 제한이 있는 compact 행 목록으로 변경했다.
- `src/model/struct/storage.py`
  - Storage overview node row에서 불필요한 `storage_note` payload를 제거했다.
- `tests/api/test_storage_models.py`
  - compact 목록 높이 제한과 불필요한 문구 제거 계약을 추가했다.

## 검증

- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_storage_models` 통과
- WIZ 프로젝트 빌드 통과: `wiz_project_build(projectName="main", clean=false)`
- devmode 쿠키를 포함한 접근 확인:
  - `https://infra-dev.nanoha.kr/access` HTTP 200
  - `https://infra-dev.nanoha.kr/storage` HTTP 200
- 정확히 지목된 문구는 테스트 금지 조건 외 프로젝트 화면/모델 코드에서 제거됨을 확인했다.

## 남은 리스크

- 실제 인증 세션에서 서버 수가 매우 많은 데이터로 스크롤 목록의 체감 높이를 직접 확인하지는 않았다.
