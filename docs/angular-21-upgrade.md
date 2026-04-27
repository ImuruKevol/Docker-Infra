# Angular 21 및 WIZ 변경 요약

이 문서는 2026-04-28 기준으로 WIZ Sample Project를 Angular 21 기반으로 올리면서 함께 바뀐 런타임, WIZ 객체, 백엔드 호환 계층을 정리한 요약 문서다.

---

## 한눈에 보기

- Angular 런타임과 빌드 도구를 21 계열로 올렸다.
- `zone.js`를 제거하고 zoneless change detection으로 전환했다.
- `wiz.call()`은 jQuery AJAX 대신 `fetch()`를 사용한다.
- JSON body를 읽을 수 있도록 `wiz.request.query()`를 base controller에서 오버라이드했다.
- Angular 21에서 정식 흐름으로 자리잡은 `signal`, `computed`, `set`, `update` 예시를 대시보드에 추가했다.
- WIZ 생성 컴포넌트는 `standalone: false`를 명시하고 기존 `AppModule` 선언 스코프를 유지한다.
- navbar에 전역 언어 전환과 다크 모드 토글을 추가하고, `service.theme`으로 앱 전체 테마 상태를 관리한다.

---

## 버전 변경

주요 프론트엔드 버전은 다음 기준으로 정리되었다.

- Angular: 18 -> 21
- Angular CLI / build-angular / compiler-cli: 18 -> 21
- TypeScript: 5.5 -> 5.9
- ng-bootstrap: 17 -> 20
- ng-util/monaco-editor: 18 -> 21
- ngx-translate/core, http-loader: 구버전 -> 17

직접 제거한 의존성:

- `zone.js`
- `jquery`

핵심 파일:

- `src/angular/package.json`
- `package.json`

---

## Angular 21 전환 포인트

### 1. zoneless change detection 적용

기존 Angular 18 기반 구성은 `zone.js` polyfill에 기대고 있었지만, 현재 샘플은 `zone.js` polyfill을 제거하고 bootstrap 시 no-op zone을 사용한다.

```ts
platformBrowserDynamic().bootstrapModule(AppModule, { ngZone: 'noop' })
    .catch(err => console.error(err));
```

핵심 파일:

- `src/angular/main.ts`
- `src/angular/app/app.module.ts`
- `src/angular/angular.json`

영향:

- `angular.json`의 `polyfills`에서 `zone.js`를 제거했다.
- `service.render()`를 통해 수동으로 `detectChanges()`를 호출하는 WIZ 흐름은 그대로 유지된다.
- 따라서 상태를 바꾼 뒤 화면 갱신이 필요할 때는 기존처럼 `await this.service.render()`를 명시적으로 호출해야 한다.

### 2. Monaco Editor 초기화 방식 변경

Angular 21 대응 버전의 `@ng-util/monaco-editor`는 예전의 `NuMonacoEditorModule.forRoot()` 대신 standalone component와 provider를 사용한다. 단, WIZ 생성 컴포넌트 자체를 standalone으로 만들 필요는 없다. `NuMonacoEditorComponent`는 `AppModule.imports`에 한 번 넣어 NgModule 스코프로 노출한다.

이전 개념:

```ts
NuMonacoEditorModule.forRoot({ baseUrl: `lib` })
```

현재 개념:

```ts
imports: [
    NuMonacoEditorComponent,
]
providers: [
    provideNuMonacoEditorConfig({ baseUrl: `lib` }),
]
```

핵심 파일:

- `src/angular/app/app.module.ts`

### 3. Angular signal 예시 추가

샘플 대시보드에서 signal 기반 상태 관리 예시를 추가했다.

```ts
public stats = signal<any[]>([]);
public loading = signal<boolean>(true);

public publishedRate = computed(() => {
    const total = this.totalPosts();
    if (total <= 0) return 0;
    return Math.round(this.publishedPosts() / total * 100);
});
```

템플릿에서는 signal 값을 함수 호출로 읽는다.

```pug
div(*ngIf="loading()") 로딩 중...
div(*ngFor="let stat of stats()")
    | {{stat.label}}
```

상태 갱신은 `.set()` 또는 `.update()`로 수행한다.

```ts
this.stats.set(data.stats || []);
this.signalCount.update((value) => value + 1);
```

핵심 파일:

- `src/app/page.dashboard/view.ts`
- `src/app/page.dashboard/view.pug`

### 4. WIZ 생성 컴포넌트와 standalone 정책

Angular 19 이후 `@Component`는 `standalone`을 명시하지 않으면 기본적으로 standalone 컴포넌트로 해석된다. Angular 21 업그레이드 후 WIZ 컴포넌트 태그가 plain element처럼 남았던 원인도 `zone.js` 제거가 아니라 이 컴포넌트 스코프 변화와 AOT 빌드가 맞물린 결과였다.

최종 정책은 다음과 같다.

- WIZ 빌더가 생성하는 Source App, Portal App, Layout, Component는 `standalone: false`를 명시한다.
- 모든 생성 컴포넌트는 기존처럼 `AppModule.declarations`에 등록한다.
- `FormsModule`, `RouterModule`, `TranslateModule`, `NuMonacoEditorComponent`처럼 여러 WIZ 앱에서 쓰는 의존성은 `AppModule.imports`에 전역으로 둔다.
- 각 WIZ 컴포넌트가 `TranslateModule` 같은 공통 의존성을 `@dependencies`로 반복 선언하지 않는다.
- `@dependencies`는 특정 앱만 필요로 하는 예외 모듈을 `AppModule.imports`에 추가해야 할 때만 사용한다.

생성 컴포넌트 개념:

```ts
@Component({
    selector: 'wiz-portal-post-detail',
    templateUrl: './view.html',
    standalone: false,
})
export class PortalPostDetailComponent { }
```

이 방향이 WIZ 프로젝트에 더 맞는 이유:

- WIZ는 여러 Source/Portal 앱을 빌드 시점에 하나의 Angular 앱으로 합성한다.
- Portal 컴포넌트 태그를 여러 페이지에서 자유롭게 쓰는 구조라 NgModule 스코프가 더 단순하다.
- 전역 서비스, 전역 pipe, 공통 UI 모듈을 `AppModule` 중심으로 관리할 수 있어 샘플 프로젝트의 학습 비용이 낮다.
- Angular 21 최적화(AOT, esbuild, zoneless)와 충돌하지 않는다. 핵심은 `standalone: false`를 명시해 Angular의 기본 standalone 해석을 막는 것이다.

핵심 파일:

- `plugin/workspace/model/builder.py`
- `src/angular/app/app.module.ts`

---

## WIZ 프론트엔드 객체 변경

### `wiz.call()`

가장 큰 변화는 `wiz.call()`의 내부 구현이다.

이전:

- 내부적으로 `$.ajax()` 사용
- 기본적으로 form encoded 방식과 유사한 요청 흐름

현재:

- 내부적으로 `fetch()` 사용
- 기본 body가 일반 객체이면 JSON으로 직렬화
- `FormData`, `URLSearchParams`, `Blob`는 그대로 전송
- 응답은 JSON 우선 파싱, 실패 시 text로 처리
- 반환 형식은 기존 사용 코드를 깨지 않도록 여전히 `{ code, data }` 형태 유지

현재 동작 요약:

```ts
const { code, data } = await wiz.call("overview");
```

내부 규칙:

- `body`가 truthy이면 기본 메서드는 `POST`
- 일반 객체는 `Content-Type: application/json`
- `body`가 falsy이면 전달한 `options` 기준으로 일반 `fetch()` 수행
- 네트워크 예외는 `{ code: 500, data: error }`로 감싼다

주의할 점:

- 기존처럼 `wiz.call("name")`만 호출해도 기본 body가 `{}`라서 `POST` JSON 요청으로 나간다.
- 정말 body 없는 `GET`이 필요하면 `wiz.call("name", null, { method: "GET" })`처럼 호출해야 한다.

핵심 파일:

- `src/angular/wiz.ts`

### 바뀌지 않은 메서드

아래 메서드는 역할 자체는 유지된다.

- `wiz.app(namespace)`
- `wiz.dev()`
- `wiz.project()`
- `wiz.socket()`
- `wiz.url(function_name)`

즉, 호출 방식 자체보다 `wiz.call()`의 전송 계층이 바뀌었다고 보면 된다.

---

## WIZ 백엔드 호환 계층 변경

`wiz.call()`이 JSON 요청을 보내도록 바뀌었기 때문에, 서버 쪽도 JSON body를 읽을 수 있어야 했다. 이를 위해 base controller에서 `wiz.request.query()`를 덮어썼다.

현재 동작:

- `GET` 요청은 `request.args.to_dict()` 사용
- 그 외 메서드는 `request.is_json`이면 `request.get_json(silent=True)` 사용
- JSON이 아니면 `request.form.to_dict()` 사용
- 필수 파라미터로 `True`를 넘긴 경우 키가 없으면 `400` 응답

개념 코드:

```py
def query(key=None, default=None):
    method = wiz.request.method().upper()
    if method == "GET":
        body = request.args.to_dict()
    else:
        if request.is_json:
            body = request.get_json(silent=True) or {}
        else:
            body = request.form.to_dict()
```

핵심 파일:

- `src/controller/base.py`
- `src/portal/season/controller/base.py`
- `src/portal/post/controller/base.py`

### 왜 Portal post에 controller를 추가했나

Portal App은 controller가 비어 있으면 위 오버라이드를 타지 않는다. 그래서 `portal/post` 패키지의 앱 API도 fetch JSON 요청을 읽을 수 있도록 base controller를 추가했다.

관련 변경:

- `src/portal/post/portal.json`: `use_controller` 활성화
- `src/portal/post/app/list/app.json`: `controller: "base"`
- `src/portal/post/app/detail/app.json`: `controller: "base"`

이 패턴은 이후 새 Portal App API를 추가할 때도 그대로 적용하면 된다.

---

## 프론트엔드 유틸 변경

### `service.theme`

전역 라이트/다크 테마 상태를 관리하는 helper를 추가했다. 현재 테마는 `localStorage`의 `season-theme`에 저장되고, `html`/`body`에 `dark` 클래스로 반영된다.

화면 스타일은 가능하면 TypeScript helper로 class 문자열을 고르지 않고 Tailwind의 `dark:` variant를 사용한다. Tailwind v4 환경에서는 `src/angular/tailwind.css`에 class 기반 dark variant를 선언해 `html.dark` 아래에서 `dark:*` 클래스가 적용되도록 했다.

기본 사용:

```ts
await this.service.theme.toggle();
await this.service.theme.set(true);

const dark = this.service.theme.isDark();
```

템플릿 스타일링:

```pug
div(class="bg-white text-zinc-950 dark:bg-zinc-950 dark:text-zinc-100")
```

테마 변경 시 `service.event.call('theme.change')`가 호출된다. 일반 UI는 Tailwind CSS가 즉시 처리하므로 이벤트 구독이 필요 없다. Monaco Editor처럼 내부 JS 옵션을 다시 만들어야 하는 컴포넌트만 이 이벤트를 구독해 갱신한다.

현재 샘플 적용:

- navbar에서 KO/EN 언어 전환과 다크 모드 토글 제공
- layout shell과 navbar에 Tailwind `dark:` 기반 전역 dark 배경 적용
- 글 작성 화면의 Monaco Editor가 전역 dark mode에 맞춰 `vs`/`vs-dark` 테마 전환

핵심 파일:

- `src/portal/season/libs/src/theme.ts`
- `src/portal/season/libs/service.ts`
- `src/angular/tailwind.css`
- `src/app/component.nav.sidebar/view.ts`
- `src/app/component.nav.sidebar/view.pug`
- `src/app/layout.sidebar/view.pug`
- `src/angular/styles/styles.scss`

### `Request` 유틸

`src/portal/season/libs/util/request.ts`도 jQuery 기반 POST에서 fetch 기반 POST로 변경했다.

의미:

- 서비스 내부의 인증 체크 같은 공통 요청도 브라우저 기본 API를 사용한다.
- 응답 포맷은 `wiz.call()`과 비슷하게 `{ code, data }` 형태를 유지한다.

### `File` 유틸

`src/portal/season/libs/util/file.ts`는 두 가지가 바뀌었다.

- 파일 선택 input 생성: jQuery 문자열 템플릿 대신 DOM API 사용
- 업로드: `$.ajax()` 대신 `XMLHttpRequest` 사용

업로드는 진행률 이벤트가 필요해서 fetch 대신 XHR을 유지했다.

---

## 실무적으로 기억할 점

### API 호출

- 일반 객체를 넘기면 이제 JSON POST다.
- 서버는 controller에서 `wiz.request.query()` 오버라이드를 타야 한다.
- controller가 없는 Portal App API는 JSON body를 못 읽을 수 있다.

### 화면 갱신

- zoneless라고 해서 WIZ의 `service.render()` 패턴이 사라진 것은 아니다.
- 이벤트 핸들러, 비동기 응답 처리 뒤에는 여전히 `await this.service.render()`가 필요하다.

### Angular 모듈 스코프

- WIZ 생성 컴포넌트는 기본적으로 standalone으로 만들지 않는다.
- Angular 21에서는 반드시 `standalone: false`를 명시해 NgModule 선언 컴포넌트임을 분명히 한다.
- 공통 pipe/directive/component 의존성은 `AppModule.imports`에 둔다.
- 컴포넌트마다 `TranslateModule`을 반복 선언하지 않는다.

### template에서 signal 읽기

- 클래스에서는 `this.signalName()`
- 템플릿에서도 `signalName()`
- 배열/객체 signal은 직접 값처럼 쓰지 않고 함수 호출 결과를 사용한다.

---

## 추천 마이그레이션 규칙

새 앱이나 기능을 추가할 때는 아래 규칙을 기준으로 맞추면 된다.

1. Angular 상태는 가능하면 `signal`, `computed` 중심으로 작성한다.
2. 서버 호출은 `wiz.call()` 또는 fetch 기반 공통 유틸을 사용한다.
3. JSON body를 받을 API는 반드시 controller 경로에서 `wiz.request.query()` 오버라이드를 타게 한다.
4. zoneless 환경에서도 상태 변경 뒤 `service.render()`를 빠뜨리지 않는다.
5. WIZ 앱 컴포넌트는 `standalone: false`로 생성하고 `AppModule.declarations` 스코프를 유지한다.
6. 다국어, Forms, Router, Monaco 같은 공통 의존성은 `AppModule.imports`에서 관리한다.
7. 전역 테마 상태는 `service.theme`을 사용하고, 개별 화면은 필요한 경우 `theme.change` 이벤트만 구독한다.

---

## 관련 파일 빠른 참조

- `src/angular/package.json`
- `src/angular/angular.json`
- `src/angular/app/app.module.ts`
- `src/angular/main.ts`
- `src/angular/wiz.ts`
- `src/controller/base.py`
- `src/portal/season/controller/base.py`
- `src/portal/post/controller/base.py`
- `src/portal/season/libs/src/theme.ts`
- `src/portal/season/libs/service.ts`
- `src/app/page.dashboard/view.ts`
- `src/app/page.dashboard/view.pug`
