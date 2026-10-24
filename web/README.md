# CMUCal web

The Next.js frontend for [cmucal.com](https://cmucal.com), written in
TypeScript with Tailwind CSS. It talks to the Flask API in [`api/`](../api).

To run it, follow [`docs/getting-started.md`](../docs/getting-started.md).
`npm run dev` starts the dev server on http://localhost:3000 together with the
local sign-in relay on port 8090 (`scripts/dev-relay.js`);
`npm run dev:next` starts only the dev server.

## Checks

```bash
npm test         # vitest
npm run check    # eslint and tsc
```

## Deployment

Kennel builds and deploys `main` to cmucal.com; see the root
[README](../README.md#deployment).
