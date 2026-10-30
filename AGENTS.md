# Repository Instructions

These instructions apply to the entire repository. More specific `AGENTS.md` files in subdirectories may add requirements but must not weaken `AI_POLICY.md`.

## Before making changes

1. Read this file, the root `AI_POLICY.md`, and `home-assistant.md` before changing code or workflows.
2. Inspect the relevant implementation, tests, configuration, and Git history before proposing a fix. Follow existing architecture and avoid unrelated changes.
3. Treat `AI_POLICY.md` as the repository's authoritative policy. If instructions conflict, follow the higher-priority instruction and explain material conflicts.
4. Do not claim to have inspected files, run checks, or verified behavior unless you actually did so.

## Scope and implementation

- Keep changes focused, maintainable, and compatible with the repository's supported Home Assistant and Python versions.
- Preserve existing public behavior unless the task explicitly requests a behavior change.
- Prefer small, cohesive functions with descriptive names and explicit control flow.
- Refactor functions to keep **cognitive complexity at or below 15**. Split complex logic into well-named private helpers without changing behavior.
- Validate untrusted API payloads at the boundary. Do not assume external fields are present, non-null, or of the expected type.
- Provide actionable error messages while avoiding credentials, tokens, personal data, and sensitive API payloads in logs.
- Do not introduce dependencies without demonstrating that they are necessary and compatible.
- Keep documentation and translations synchronized with user-visible behavior changes.

## Python conventions

- Follow the detailed rules in `home-assistant.md`.
- Use type hints for functions and methods, and docstrings for modules, classes, and functions/methods.
- Use modern Python syntax supported by the repository's declared minimum version; do not raise that minimum without an explicit reason.
- Use `snake_case` for variables and functions, and prefix class-internal helper methods with an underscore.
- Use lowercase `list` and `dict` annotations; do not import `List` or `Dict`.
- Use lazy %-style formatting in logging calls, for example `_LOGGER.debug("Loaded %s records", count)`.
- Use timezone-aware datetimes. Avoid deprecated APIs and floating-point equality comparisons; use tolerances or suitable numeric comparison helpers when comparing measured floating-point values.
- Do not reuse a function parameter name for a local variable or shadow names from an outer scope unnecessarily.
- Keep exception handling consistent. Catch specific exceptions where practical, preserve exception context, and do not silently suppress failures.
- Add input validation where it protects data integrity and report invalid input clearly.
- Use two blank lines before top-level function definitions and keep formatting consistent with the project's formatter and linter.

## Home Assistant integration requirements

- Follow `home-assistant.md` and current Home Assistant APIs supported by this repository.
- Use config entries and the existing coordinator architecture. Avoid duplicate API clients, polling loops, or per-entity network requests.
- Keep setup, unload, reload, and listener cleanup symmetrical. Register cleanup callbacks for listeners and other resources.
- Use asynchronous APIs for I/O. Never perform blocking network, filesystem, or subprocess operations on the event loop.
- Preserve isolation between config entries. Store per-entry runtime data by `entry.entry_id`; do not merge accounts or devices accidentally.
- Keep entity unique IDs stable and device identifiers and `via_device` references valid. Do not create orphaned devices or entities.
- Create gas-related entities only when the account has an active gas contract; handle contract changes and stale registry entries safely.
- Handle missing, `None`, malformed, and unexpected API values without making unrelated entities unavailable.
- Keep manifest metadata, translations, entity descriptions, diagnostics, and documentation aligned with implementation.

## Pull requests and review comments

- Read all relevant review comments, including CodeRabbit comments, before changing a reviewed pull request.
- Address valid review findings and requested fixes; do not dismiss comments without checking them against the current code and repository policy.
- After making changes to a pull request, trigger or request a fresh review when the repository's available workflow supports it. Do not claim a review was triggered unless confirmed.
- Recheck comments after revisions and resolve a thread only after its concern has been addressed.
- Keep pull requests focused and describe behavior changes, tests, and any remaining limitations.

### When GitHub reports `rebaseable: false`

- Check `rebaseable` separately from `mergeable`: `mergeable: true` does not prove that GitHub can rebase the branch. Fetch the latest pull-request head and target branch before diagnosing the conflict.
- Preserve the current head in a backup branch before rewriting history. Resolve conflicts by rebasing onto the current target branch, or rebuild the reviewed changes as linear commits on that target when merge history prevents rebasing. Merging the target into the pull-request branch alone is not sufficient evidence that rebasing works.
- Inspect the resulting diff to preserve the reviewed changes and unrelated updates on the target branch. For a history-only rewrite with an unchanged target, verify that the new commit's file tree matches the previously tested tree exactly.
- Update the branch with `git push --force-with-lease` or an API update guarded by the expected previous head SHA. If the head changed concurrently, fetch and reconcile those changes before retrying.
- Run the applicable tests and CI checks and request a fresh review through the configured tooling. Before reporting the problem as resolved, fetch the pull request again and verify `rebaseable: true` for the exact final head SHA; report this separately from ordinary mergeability.

## Verification

Use the checks defined by the current repository workflows and README. At minimum, for relevant changes:

- Run the focused pytest tests, then the full test suite when feasible.
- Run Ruff using the repository configuration.
- Run Home Assistant's `hassfest` and HACS validation when integration metadata, translations, manifest, or packaging changes.
- Inspect the final diff for accidental changes, missing tests, secrets, and stale documentation.

If a check cannot be run, state why and distinguish unverified checks from passing checks. Never fabricate test results.
