# Central Repo-Standards Check — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish, in `pipepath/.github`, the reusable workflow `repo-standards.yml` and the verifier
copy it runs, make this repository conform to the standard it enforces, prove that a private repository
of the organization can call the workflow, and record the central SHA the rollout pins.

**Architecture:** `repo-standards/` holds a byte-identical copy of the hub skill's `verify.py` and
`standards/`, plus `VERSION` (the hub commit those files come from). `.github/workflows/repo-standards.yml`
is a `workflow_call` workflow that checks out the caller and this repository at `job.workflow_sha`, runs
the verifier with `--version` from `repo-standards/VERSION`, and runs gitleaks over the caller's full
history. This repository calls itself through `.github/workflows/standards.yml` like every other
repository, and its own CI runs the verifier against itself plus gitleaks.

**Tech Stack:** Python 3 standard library (the verifier); GitHub Actions YAML; Markdown (Spanish neutral).

**Spec:** `pipepath/workspaces-hub` → `docs/superpowers/specs/2026-10-17-pipepath-repo-standards-design.md`
(§2, §3.2, §3.3, §4, §6 step 5; binding).

**Depends on:** the hub plan `2026-10-17-pipepath-repo-standards-hub.md` (done); infra repository
creation (done: this repository is public and has no `PIPEPATH_RUNNER` variable, so every job here falls
back to the hosted `ubuntu-24.04`).

## Global Constraints

- Source of truth for every copied file: the hub skill `.claude/skills/repo-standards/` at the hub
  commit its `VERSION` names, as written by `/sync-rules` into the synced workspace copy
  (`b53320619b61c665f1eea27a8ed7821c815cbf91` for Task 1; the new value after Task 1A). Copies are
  byte-identical, without `__pycache__`; nothing under `repo-standards/` (except its `README.md`) or
  `.claude/skills/repo-standards/` is edited by hand.
- `repo-standards/VERSION` and `.claude/skills/repo-standards/VERSION` both contain exactly the synced
  `VERSION` bytes (40-hex SHA plus a newline).
- Canonical `runs-on` on every job:
  `${{ fromJSON(((github.event_name != 'pull_request' || github.event.pull_request.head.repo.full_name == github.repository) && github.actor != 'dependabot[bot]' && vars.PIPEPATH_RUNNER) || '"ubuntu-24.04"') }}`
- Every `uses:` pinned by a 40-hex SHA with a version comment; third-party actions at least 14 days old
  (`actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1`, as in the hub templates). The
  organization's own central workflow is pinned by SHA too; the age rule does not apply to it.
- Gitleaks image, verbatim: `ghcr.io/gitleaks/gitleaks:v8.30.1@sha256:c00b6bd0aeb3071cbcb79009cb16a60dd9e0a7c60e2be9ab65d25e6bc8abbb7f`.
- This repository is **public**: no secrets, no token-shaped literals, no PEM armor, no absolute local
  paths, no runner host names, addresses or private infrastructure details. Private repositories are
  referred to by name only.
- Human docs in Spanish neutral, < 120 lines (README) and < 150 lines (other docs), no process
  vocabulary (task numbers, review vocabulary, agent ids, work-branch names). Code, comments and commit
  messages in English.
- Flow: the empty repository's first commit (a minimal README) went straight to `main`; everything
  else goes through a branch and a PR merged with squash once CI is green and the review approved.
  Never `--no-verify`.
- Done means: `python3 repo-standards/verify.py . --version "$(cat repo-standards/VERSION)"` prints no
  FAIL, local gitleaks over the full history finds nothing, and every check of the PR is green.

---

### Task 1: Verifier copy and reusable workflow

**Files:**
- Create: `repo-standards/verify.py`, `repo-standards/standards/__init__.py`, `repo-standards/standards/ci.py`,
  `repo-standards/standards/docs.py`, `repo-standards/standards/report.py` (copied)
- Create: `repo-standards/VERSION` (copied from the synced workspace copy)
- Create: `.github/workflows/repo-standards.yml` (copied from the hub's `templates/central/repo-standards.yml`)

- [ ] **Step 1: Red.** `python3 repo-standards/verify.py .` fails (file missing).
- [ ] **Step 2:** Copy the files above. Executable bit on `verify.py` as in the source.
- [ ] **Step 3: Green.** `diff -r -x __pycache__` between the hub skill's `verify.py` + `standards/` and
  `repo-standards/` shows no difference; `VERSION` equals the synced copy's `VERSION`;
  `cmp` the workflow against the template. `python3 repo-standards/verify.py . --format json` runs
  (exit 1 is expected here: docs and CI files are still missing) and reports nothing for
  `.github/workflows/repo-standards.yml` under `runs-on`, `pinned-actions` or `workflow-parse`.
- [ ] **Step 4:** Commit `feat: add the central repo-standards verifier and reusable workflow`. Record its
  SHA: Task 2 pins `standards.yml` to it.

### Task 1A: Central gitleaks config and verifier hardening (hub first, then re-copy)

A security review of the Task 1 commit found two gaps. (1) Untrusted caller content on self-hosted
runners: the verifier must only read the caller's files (no `exec`, `eval`, `subprocess`, dynamic
import), pinned by a test; the central workflow interpolates nothing from the caller into `run:`.
(2) Control bypass: the central gitleaks step scanned the caller checkout, so gitleaks honored the
caller's own `.gitleaks.toml` and a broad caller allowlist silenced the central scan.

**Hub (straight to `main`), in `.claude/skills/repo-standards/`:**
- `gitleaks.toml`: the central base config, `[extend] useDefault = true`, no allowlists, no rules.
- `gitleaks_config.py` (stdlib; `tomllib`): reads the caller's root `.gitleaks.toml`, keeps only the
  allowlist entries that pass the `gitleaks-allowlist` rule below, and prints the base config plus those
  entries; caller `[[rules]]`, `[extend]` and per-rule allowlists are never carried over; dropped entries
  are listed on stderr. Invalid or absent caller config: base config only.
- `standards/`: new check `gitleaks-allowlist` (FAIL) on the root `.gitleaks.toml`: every global
  allowlist entry (`[allowlist]` or `[[allowlists]]`) and every per-rule allowlist has `paths`, each
  anchored `^…$` and without an unbounded wildcard (`.*`, `.+`, `.{n,}`), plus `commits`, `regexes` or
  `targetRules`; `condition = "AND"` whenever two or more of `commits`, `paths`, `regexes`, `stopwords`
  are set. `standards-workflow` also FAILs a caller job that passes `secrets:` to the central workflow.
- A test that parses `verify.py`, `gitleaks_config.py` and `standards/*.py` (AST) and fails on any
  `subprocess`, `os.system`, `os.exec*`, `os.spawn*`, `os.popen`, `exec`, `eval`, `compile`,
  `__import__`, `importlib`, `runpy`, `pickle`, `marshal`, `shelve`, `ctypes`.
- `templates/central/repo-standards.yml`: both jobs run Python with `-I`; the `gitleaks` job also checks
  out `pipepath/.github` at `job.workflow_sha`, writes the merged config to `$RUNNER_TEMP`, and runs the
  pinned image with `--config` pointing at it (mounted read-only). No `${{ }}` of caller data in `run:`.
- `SKILL.md`, the `sync-rules` section «Publicar el verificador central» (copy list: `verify.py`,
  `gitleaks_config.py`, `gitleaks.toml`, `standards/`, `VERSION`) and spec §3.3 updated.
- Hub tests green (`python3 -m unittest discover -s tests -v`), verifier coverage ≥ 90 %.

**Then:** `/sync-rules spawn-workspace` (new `VERSION`), and in this repository re-copy
`repo-standards/` and `.github/workflows/repo-standards.yml` from the new hub commit (commit
`feat: harden the central gitleaks scan and verifier`). Task 2 pins `standards.yml` to that commit.

### Task 1B: Central-only gitleaks configuration (supersedes the caller-config merge of Task 1A)

Validating a caller's `.gitleaks.toml` in Python keeps diverging from gitleaks' Go parser, so that class
is removed: **the central scan never reads the caller's gitleaks configuration.**

**This repository:**
- `gitleaks/base.toml`: `[extend] useDefault = true`, nothing else.
- `gitleaks/allow/<repo>.toml`: only `[[allowlists]]` entries, each with a reason comment, paths anchored
  `^…$` and AND-combined with `commits`, `regexes` or `targetRules`. Seeded with the confirmed false
  positives allowlisted today, anchors copied exactly: `workspaces-hub` (two commits on
  `tests/test_secret_scan.py`), `spawn-workspace` (commit `b70a50f…` on the docs-site plan),
  `spawn-control` (`jwt` on the two ticket fixtures, `fixture-1` header), `brand-app` (sha256 digests in
  `packages/brand/test/legacy-outputs.test.ts`).
- `gitleaks/empty.gitleaksignore`: empty file for `--gitleaks-ignore-path`.
- CI: a job that loads `base.toml` alone and `base.toml` + each allow file into the pinned image against an
  empty directory, so a malformed file fails the PR that adds it.

**Hub (straight to `main`):**
- Remove `gitleaks_config.py`, `gitleaks.toml`, the caller-TOML validation in `standards/gitleaks.py` and the
  `gitleaks-allowlist` check (keep the AST no-exec test and the `secrets:` caller check).
- `templates/central/repo-standards.yml`, gitleaks job: checkout the caller and `pipepath/.github` at
  `job.workflow_sha`; name = `github.repository` without the `pipepath/` owner (via `env:`, validated
  `^[A-Za-z0-9_.-]+$`, not `.`/`..`; other owners get the base only); compose
  `base.toml` + `allow/<name>.toml` (if present) with `cat` into `$RUNNER_TEMP`; remove the caller's
  `.gitleaksignore`; `* diff` in `.git/info/attributes`; run the pinned image under a clean env with
  `--config`, `--gitleaks-ignore-path` (the empty file), `--ignore-gitleaks-allow`,
  `--log-opts="--full-history --all"`, `git /repo --redact --verbose`.
- `SKILL.md` (gitleaks exceptions section), sync-rules «Publicar el verificador central» copy list, spec
  §3.2/§3.3, hub log.

**Then:** `/sync-rules spawn-workspace`; in this repository re-copy `repo-standards/` (removing the dropped
files) and the workflow, add `gitleaks/`, the CI job, update `repo-standards/README.md`, and re-pin
`standards.yml` to that commit.

### Task 1C: Fail-closed visibility and the local gitleaks files check

**Hub (straight to `main`):**
- `verify.py`: `--public` becomes `--repo-private <value>`; only the exact value `true` selects private
  mode; missing, empty, `false` or anything else selects the public rules (never default to private).
- New check `gitleaks-local`: FAIL when the repository has `.gitleaksignore` or `.gitleaks.toml` and
  `pipepath/.github` has no `gitleaks/allow/<repo>.toml` for it (local exceptions the central scan does not
  honor must move there). Inputs `--central-gitleaks <dir>` and `--repo-name <name>`; without them the
  check WARNs that it cannot confirm. The file contents are never parsed.
- Central template, verify job: `REPO_PRIVATE` and `CALLER` through `env:`; repo name derived and validated
  exactly as in the gitleaks job (shared snippet or identical, both pinned by tests); passes
  `--repo-private "$REPO_PRIVATE" --central-gitleaks central/gitleaks --repo-name "$name"`.
- A test pins the full `CHECKS` list and the exit codes (0 clean, 1 findings, 2 usage).
- `SKILL.md`, spec §3.3, hub log.

**Then:** `/sync-rules spawn-workspace`; re-copy into this repository; `ci.yml` self-check passes
`--repo-private false --central-gitleaks gitleaks --repo-name .github`; re-pin `standards.yml`.

### Task 2: This repository conforms to the standard

**Files:**
- Create: `.claude/skills/repo-standards/` (byte-identical copy of the synced workspace skill, with `VERSION`)
- Create: `.github/workflows/ci.yml` (jobs `verify`, `gitleaks`, `required`)
- Create: `.github/workflows/standards.yml` (the hub template, pinned to the Task 1A re-copy commit, comment `# set by /sync-repos`)
- Create: `.github/pull_request_template.md` (the hub template)
- Modify: `README.md`; Create: `docs/README.md`, `repo-standards/README.md`

- [ ] **Step 1: Red.** `python3 repo-standards/verify.py . --version "$(cat repo-standards/VERSION)"`
  lists the FAILs for the missing files and CI.
- [ ] **Step 2:** `ci.yml`, from the hub's `templates/github/workflows/ci.yml`: the placeholder `test` job
  becomes `verify`, whose step runs
  `python3 repo-standards/verify.py . --version "$(cat repo-standards/VERSION)"` (the PR's own verifier
  against the PR's own tree, so a broken copy fails before it is published); `gitleaks` and `required`
  unchanged except `required.needs: [verify, gitleaks]`.
- [ ] **Step 3:** Docs. `README.md` follows the template sections (what it is, why, 30 seconds, status,
  what to read, how to start with commands that exist here). `docs/README.md` has exactly
  `## Para personas` and `## Para agentes e implementación` and lists every human doc.
  `repo-standards/README.md` (component README) says what the copy is, that `/sync-rules` (section
  «Publicar el verificador central») replaces it through a PR, that nobody edits it by hand, and what
  `VERSION` means. Every cited command and path verified against the files.
- [ ] **Step 4: Green.** The verifier command above prints no FAIL; gitleaks over the full history
  (`docker run --rm -v "$PWD:/repo" <image> git /repo --redact --verbose`) finds nothing.
- [ ] **Step 5:** Commit(s) `feat: make pipepath/.github conform to the repo standard` (or split by area).

### Task 3: Public-content audit

- [ ] **Step 1:** Review every tracked file for secrets, token-shaped literals, absolute local paths,
  host names, addresses, runner names and private-repository internals beyond repository names
  (`git ls-files | xargs grep -nE ...` plus reading the docs and the plan).
- [ ] **Step 2:** Fix anything found (never obfuscate for a scanner; a confirmed false positive gets an
  anchored allowlist entry with a reason). Commit `docs: ...` / `fix: ...` if anything changed.

### Task 4: Publish (PR 1)

- [ ] **Step 1:** Push `feat/central-standards`, open the PR (body from the PR template, ending with the
  Claude Code line).
- [ ] **Step 2:** Watch the checks: `ci / verify`, `ci / gitleaks`, `ci / required`, `standards / verify`,
  `standards / gitleaks`. All green, then squash-merge. Record the merge commit (M1).

### Task 5: Pin the self-call to `main` (PR 2)

The Task 1 commit survives the squash only through the PR ref; `main` must call a commit on `main`.

- [ ] **Step 1:** Branch `fix/standards-pin-main` from `main`; set the SHA in `standards.yml` to M1.
- [ ] **Step 2:** Verifier green locally; PR; checks green; squash-merge. Record the merge commit (M2).

### Task 6: Cross-repository proof

- [ ] **Step 1:** In a private repository (`pipepath/spawn-workspace`), create a throwaway branch with a
  temporary `.github/workflows/standards.yml` that calls
  `pipepath/.github/.github/workflows/repo-standards.yml@<M2>` and triggers on `push` to that branch.
- [ ] **Step 2:** Push, watch the run: both jobs (`verify`, `gitleaks`) start, check out the caller and
  `pipepath/.github` at M2, and run to completion. Findings from the caller are expected (it has not been
  rolled out yet); a failure to resolve or check out the central workflow is a blocker. Record the run URL,
  the runner each job used and each job's result.
- [ ] **Step 3:** Delete the branch (remote and local). Never merge it.

### Task 7: Record the central SHA

- [ ] **Step 1:** The rollout pins M2 (the `main` commit whose `repo-standards/VERSION` equals the synced
  `VERSION`). Record it, with the proof run, in the hub log of the day.
