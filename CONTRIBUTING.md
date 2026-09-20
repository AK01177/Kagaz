# Contributing to Kagaz

Thank you for contributing to Kagaz.

Kagaz is developed as a team project for IT314 Software Engineering. This document defines the team's GitHub workflow so that contributions remain traceable, reviewable, and consistent.

## 1. Branch Naming

Do not work directly on the `main` branch.

Create a separate branch for each task.

Use the following naming convention:

- `feat/<short-description>` for new features
- `fix/<short-description>` for bug fixes
- `docs/<short-description>` for documentation
- `test/<short-description>` for testing work
- `refactor/<short-description>` for refactoring
- `chore/<short-description>` for maintenance/setup
- `ci/<short-description>` for CI/CD changes

Examples:

```text
feat/document-upload
feat/document-classification
fix/upload-validation
docs/architecture
test/classification-tests
chore/setup-backend
ci/backend-tests
```

Keep branch names short and descriptive.

## 2. Commit Naming

Use clear and consistent commit messages.

Recommended format:

```text
<type>: <short description>
```

Common commit types:

- `feat:` new functionality
- `fix:` bug fix
- `docs:` documentation
- `test:` tests
- `refactor:` code restructuring
- `chore:` maintenance or configuration
- `ci:` CI/CD changes

Examples:

```text
feat: add document upload endpoint
fix: validate unsupported file types
docs: add architecture documentation
test: add classification API tests
chore: initialize backend project
ci: add backend test workflow
```

Commits should describe one logical change whenever possible.

## 3. Pull Request Rules

All meaningful changes should be submitted through a Pull Request.

Before opening a PR:

1. Make sure the branch is up to date with `main`.
2. Review your own changes.
3. Remove debugging code and unnecessary files.
4. Run the relevant tests.
5. Check that no secrets or credentials are included.
6. Link the related GitHub Issue.

PR titles should be concise and descriptive.

Example:

```text
feat: implement document upload API
```

A PR should contain:

- What was changed
- Why it was changed
- Related Issue
- Testing performed
- Any known limitations

## 4. Issue Linking

Every task should have a GitHub Issue whenever practical.

Reference the issue in the Pull Request or commit.

Examples:

```text
Closes #12
```

or:

```text
Fixes #12
```

Use the issue number so that the implementation remains traceable to the planned requirement or task.

## 5. Review Expectations

At least one team member should review a Pull Request before it is merged when practical.

Reviewers should check:

- Correct functionality
- Code readability
- Appropriate naming
- Tests
- Error handling
- Security concerns
- No unrelated changes
- No exposed secrets
- Issue linkage

The author should address important review comments before merging.

Do not merge a Pull Request simply because the code appears to work locally.

## 6. Testing Before PR

Before opening a Pull Request:

1. Run the relevant tests.
2. Check the application locally.
3. Verify the changed functionality.
4. Check for obvious regressions.
5. Include testing details in the PR description.

For backend changes, run the backend test suite.

For frontend changes, verify the affected UI flow.

For AI-related changes, test representative sample documents and record important limitations or unexpected outputs.

## 7. Secrets Policy

Never commit secrets to GitHub.

Do not commit:

- API keys
- Passwords
- Database credentials
- Access tokens
- Private keys
- `.env` files containing real credentials
- Service account credentials

Use environment variables for secrets.

Example:

```text
OPENAI_API_KEY=...
DATABASE_URL=...
```

Real secret values must remain local or in the approved deployment secret store.

If a secret is accidentally committed, notify the project lead immediately and rotate/revoke the exposed credential.

## 8. General Team Rules

- Keep changes focused on the assigned Issue.
- Avoid unrelated modifications in the same PR.
- Keep documentation updated when behavior or architecture changes.
- Communicate blockers in the team's designated Slack channel.
- Use GitHub Issues and Projects as the source of task status.
- Preserve individually attributable commits for project evaluation.

## 9. Basic Workflow

The normal workflow is:

```text
GitHub Issue
     ↓
Create branch
     ↓
Implement task
     ↓
Test locally
     ↓
Commit changes
     ↓
Push branch
     ↓
Open Pull Request
     ↓
Code review
     ↓
Address feedback
     ↓
Merge
     ↓
Close/complete Issue
```

The `main` branch should contain reviewed and usable work.
