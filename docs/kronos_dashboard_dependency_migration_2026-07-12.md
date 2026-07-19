# Kronos Dashboard 직접 의존성 마이그레이션 — 2026-07-12

## 범위와 목적

Todo 22의 변경 범위 안에서 감사된 Svelte/Vite 대시보드의 직접 의존성만 갱신했다. 목적은 Todo 11 이후 남은 정적·호환성·보안 부채를 닫는 것이다. 컴포넌트 API나 제품 동작을 재설계하지 않았고 간접 패키지를 임의로 고정하지 않았다.

| 패키지 | 이전 범위 | 새 범위 | lockfile 해석 버전 |
|---|---:|---:|---:|
| `echarts` | `^5.5.0` | `^6.1.0` | `6.1.0` |
| `vite` | `^5.4.0` | `^7.3.6` | `7.3.6` |
| `@sveltejs/vite-plugin-svelte` | `^4.0.0` | `^6.2.4` | `6.2.4` |

Vite 7과 Svelte 플러그인 6의 지원 범위에 맞춰 Node 엔진을 `^20.19 || ^22.12`로 좁혔다. npm 엔진은 기존대로 9·10·11을 지원한다.

## 호환성 판단

- 현재 Svelte 5, TypeScript, PostCSS, Tailwind 구성은 유지했다.
- ECharts 6에서 현재 대시보드가 사용하는 `echarts.init`, option, resize, dispose 계약은 변경 없이 통과했다. 별도의 컴포넌트 API 마이그레이션은 필요하지 않았다.
- Vite 설정과 빌드 진입점은 변경하지 않았다.
- lockfile은 `npm ci`가 재현 가능한 설치를 수행하도록 함께 갱신했다.
- 빌드의 chunk-size advisory는 오류나 보안 취약점이 아니며 기존 기능을 차단하지 않는다.

## 현재 검증

`webui/v2_src`에서 다음을 실행했다.

```text
npm ci
npm run check
npm run build
npm audit --json
```

결과:

- `svelte-check`: 284 files, 0 errors, 0 warnings
- Vite 7.3.6 production build: 성공, 827 modules transformed
- npm audit: critical 0, high 0, moderate 0, low 0
- 변경된 Python/TS/Svelte 및 지정 감사 파일의 LSP error 진단: 0

원본 명령 출력은 `.omo/evidence/task-22-static-deps/`에 보존한다.

## 운영 경계와 롤백

이 변경은 로컬 연구 대시보드를 인터넷 서비스로 바꾸지 않으며 CORS, 라우트, 데이터 경로, 거래 기능을 변경하지 않는다. 문제가 발생하면 `webui/v2_src/package.json`과 `package-lock.json`을 이 원자적 커밋 이전 상태로 함께 되돌리고 `npm ci && npm run check && npm run build`로 확인한다. 생성된 `dist`는 소스 수정 대상이 아니며 Todo 24의 최종 소스 동결 뒤 한 번만 재생성한다.
