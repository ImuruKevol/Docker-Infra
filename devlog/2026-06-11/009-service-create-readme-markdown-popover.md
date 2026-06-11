# 009 서비스 생성 README 팝오버 마크다운 렌더링 적용

- 날짜: 2026-06-11
- 리뷰 ID: hhxtqfhtxsmqabkdfkqaljcwelvrfozn

## 사용자 원 요청

- README 팝오버에 표시되는 텍스트는 agent 컴포넌트들에 적용된 수준의 마크다운 스타일을 적용해서 보여줄 것.

## 변경 파일

- `src/app/page.services.create/view.pug`
- `src/app/page.services.create/view.ts`
- `src/app/page.services.create/view.scss`
- `devlog.md`
- `devlog/2026-06-11/009-service-create-readme-markdown-popover.md`

## 변경 내용

- README 팝오버 본문을 `pre` 원문 출력에서 `innerHTML` 기반 마크다운 렌더링으로 변경했다.
- agent 응답 렌더링과 같은 수준의 heading, paragraph, list, inline code, code block, table 변환 로직을 서비스 생성 페이지에 추가했다.
- 렌더링 전 HTML escape를 수행하고, Angular `DomSanitizer`로 trusted HTML을 반환하도록 했다.
- `service-readme-markdown ai-agent-markdown` 스타일을 추가해 agent 마크다운과 같은 font size, line-height, heading/list/code/table 스타일을 적용했다.

## 검증 결과

- 성공: WIZ project build `main`
- 성공: 실제 브라우저에서 인증 후 `season-wiz-project=main`, `season-wiz-devmode=true` 쿠키로 `/services/create` 검증.
- 확인: README 팝오버 본문이 `pre`가 아닌 `.service-readme-markdown.ai-agent-markdown`으로 렌더링됨.
- 확인: README 내용에서 heading, paragraph, list, inline code가 HTML 태그로 변환됨.
- 확인: computed style 기준 본문 `font-size: 13px`, `line-height: 21.06px`, heading `font-size: 13px`, inline code `font-size: 12px`로 적용됨.
