## Summary

<!-- What does this change do, and why? -->

## Changes

-

## Read-only Git safety

- [ ] No mutating Git subcommand added (`READ_ONLY_SUBCOMMANDS` unchanged, or only read-only additions)
- [ ] No new network access (or limited to `clone_bare`, `fetch_pull_ref`, `fetch_pull_meta`)
- [ ] Client text is never passed to Git as a revision or path without validation
- [ ] Repository content is rendered as plain text only

## Testing

- [ ] Backend: `cd backend && .venv/Scripts/python -m pytest`
- [ ] Frontend: `cd frontend && pnpm test -- --run && pnpm build`
- [ ] New endpoints have service tests; security-relevant changes have a `test_security.py` test
- [ ] Checked manually in the browser (describe below)

<!-- Manual check, screenshots, or output -->

## Release

Merging into `master` tags a release automatically. Add **one** label to choose the version bump:
`major`, `minor`, `patch` (the default when unlabelled), or `skip` for no release.

## Docs

- [ ] README / roadmap updated if behaviour or limitations changed
- [ ] `frontend/src/types/git.ts` and Pydantic schemas changed together
