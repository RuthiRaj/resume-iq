# Resume IQ: agent rules

## Stack
- frontend/: Next.js 15, Playwright e2e (Node 22)
- backend/: FastAPI, pytest
- Firebase: Auth, Firestore, Storage (project resumeiq-3cfe6)

## Commands
- Frontend: `cd frontend; npm ci; npx tsc --noEmit; npm run lint; npm run build`
- E2E: build with NEXT_PUBLIC_E2E=true and NEXT_PUBLIC_E2E_TEST_MODE=true, then `npx playwright test`
- Backend: `cd backend; pip install -r requirements.txt; pytest -q`

## Git rules
- `main` is protected. Never push to it. Work on a short branch, open a PR, wait for 4 green checks.
- Never force-push, never delete remote branches, never merge into main. The owner does that.
- One task per branch. Commit messages: `type(scope): summary`.

## Safety rules
- Never read or print .env files or secrets.
- E2E mock code must stay behind NEXT_PUBLIC_E2E. CI greps the production bundle for `__E2E_MOCK`.
- Use the Firebase emulator for anything that writes data. Never mutate the live project.
- Report before committing when a task says "stop and report".
