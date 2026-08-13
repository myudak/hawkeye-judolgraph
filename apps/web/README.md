# HAWK-EYE frontend

React 19, TypeScript, Vite, Tailwind CSS v4, and shadcn/ui presentation layer for the localhost
HAWK-EYE investigator console.

The frontend consumes the existing same-origin FastAPI endpoints. It does not define collection,
evidence, graph, candidate, assertion, or review truth. `npm run build` writes a deterministic
entry and content-hashed lazy route chunks to `apps/api/src/hawkeye/review_app/static/`, which the loopback-only
FastAPI server continues to serve. See `../../docs/architecture/FRONTEND.md` for the truth/projection boundary.

```powershell
npm ci
npm run format:check
npm run typecheck
npm run lint
npm run test
npm run build
```
