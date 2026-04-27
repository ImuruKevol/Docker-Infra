# Angular 21 및 WIZ 변경 요약

이 문서는 2026-04-27 기준으로 WIZ Sample Project를 Angular 21 기반으로 올리면서 함께 바뀐 런타임, WIZ 객체, 백엔드 호환 계층을 정리한 요약 문서다.

---

## 한눈에 보기

- Angular 런타임과 빌드 도구를 21 계열로 올렸다.
- `zone.js`를 제거하고 zoneless change detection으로 전환했다.
- `wiz.call()`은 jQuery AJAX 대신 `fetch()`를 사용한다.
- JSON body를 읽을 수 있도록 `wiz.request.query()`를 base controller에서 오버라이드했다.
- Angular 21에서 정식 흐름으로 자리잡은 `signal`, `computed`, `set`, `update` 예시를 대시보드에 추가했다.

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

기존 Angular 18 기반 구성은 `zone.js` polyfill에 기대고 있었지만, 현재 샘플은 `provideZonelessChangeDetection()`을 사용한다.

```ts
providers: [
    provideZonelessChangeDetection(),
    provideNuMonacoEditorConfig({ baseUrl: `lib` }),
]
```

핵심 파일:

- `src/angular/app/app.module.ts`
- `src/angular/angular.json`

영향:

- `angular.json`의 `polyfills`에서 `zone.js`를 제거했다.
- `service.render()`를 통해 수동으로 `detectChanges()`를 호출하는 WIZ 흐름은 그대로 유지된다.
- 따라서 상태를 바꾼 뒤 화면 갱신이 필요할 때는 기존처럼 `await this.service.render()`를 명시적으로 호출해야 한다.

### 2. Monaco Editor 초기화 방식 변경

Angular 21 대응 버전의 `@ng-util/monaco-editor`는 예전의 `NuMonacoEditorModule.forRoot()` 대신 standalone component와 provider를 사용한다.

이전 개념:

```ts
NuMonacoEditorModule.forRoot({ baseUrl: `lib` })
```

현재 개념:

```ts
imports: [NuMonacoEditorComponent]
providers: [provideNuMonacoEditorConfig({ baseUrl: `lib` })]
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

---

## 관련 파일 빠른 참조

- `src/angular/package.json`
- `src/angular/angular.json`
- `src/angular/app/app.module.ts`
- `src/angular/wiz.ts`
- `src/controller/base.py`
- `src/portal/season/controller/base.py`
- `src/portal/post/controller/base.py`
- `src/app/page.dashboard/view.ts`
- `src/app/page.dashboard/view.pug`
