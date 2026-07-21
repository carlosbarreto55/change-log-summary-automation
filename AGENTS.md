# Agent Instructions

These instructions apply to all work in this repository.

## Coding Standards

- Follow YAGNI: do not add abstractions, configuration, compatibility layers, or extension points until they are required by the current task.
- Follow SOLID principles when designing classes, modules, and function boundaries.
- Prefer the smallest correct implementation that satisfies the current tested behavior.
- Keep behavior explicit and readable before optimizing for reuse.

## Testing Standards

- All new code must be tested before it is considered complete.
- Do not commit a new feature, mark a task as done, or mark a plan item complete while any new code is untested.
- Untested code means the feature is incomplete.
- Tests are not limited to unit tests; integration tests are required for behavior that crosses module, filesystem, Git, configuration, or workflow boundaries.
- Keep class-level/unit tests separate from context/integration tests.
- Integration tests must use the public Linux kernel repository (`git@github.com:torvalds/linux.git`) as the external repository fixture.
- Integration test configuration must be defined in JSON files.
- Runtime code must accept a configuration file path as a function parameter instead of relying on hard-coded test or project configuration.

## Git Conventions

- Always branch from `main` before starting a new task.
- Task branches must use conventional branch names, such as `feat/<short-description>`, `fix/<short-description>`, `docs/<short-description>`, or `test/<short-description>`.
- Never push directly from `main` or `dev`.
- Work must be pushed from a task branch and merged through a pull request.
- Commits must use Conventional Commits, such as `feat: add config loader`, `fix: handle missing release marker`, or `docs: update project instructions`.
- Commit messages for project work must include a `Changes:` section listing the changes made.
- Do not commit if tests required by the change have not been added and run successfully.
