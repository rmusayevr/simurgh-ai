## What does this PR do?

<!-- A clear, concise summary of the change. Link the related issue if there is one. -->

Closes # <!-- issue number, if applicable -->

---

## Type of change

- [ ] Bug fix
- [ ] New feature
- [ ] Refactor (no behaviour change)
- [ ] Documentation only
- [ ] Chore (dependencies, tooling, config)

---

## Checklist

### Code quality
- [ ] `ruff check .` passes (no lint errors)
- [ ] `ruff format . --check` passes (no formatting changes needed)
- [ ] `npx tsc --noEmit` passes on the frontend
- [ ] `npm run lint` passes on the frontend

### Tests
- [ ] All existing tests pass: `pytest tests/unit/ -v`
- [ ] New code has tests (unit tests at minimum)

### Database
- [ ] No SQLModel model was changed  
      _— or —_  
- [ ] An Alembic migration is included and has been tested (`upgrade head` + `downgrade -1` + `upgrade head`)

### Types
- [ ] No new backend enums were added  
      _— or —_  
- [ ] New enums are mirrored in `frontend/src/types/index.ts`

### Documentation
- [ ] `CHANGELOG.md` updated under `[Unreleased]`
- [ ] `docs/` or `README.md` updated if behaviour changed

### Security
- [ ] No secrets, API keys, or `.env` files included in this commit
- [ ] User input that reaches the AI layer is validated/sanitised

---

## How to test this

<!-- Step-by-step instructions for a reviewer to verify the change works. -->

1. 
2. 
3. 

---

## Screenshots (if UI change)

<!-- Before / after screenshots help reviewers a lot. Delete this section if not applicable. -->