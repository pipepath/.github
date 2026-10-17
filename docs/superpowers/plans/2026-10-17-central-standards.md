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

- Source of truth for every copied file: the hub skill `.claude/skills/repo-standards/` at hub commit
  `b53320619b61c665f1eea27a8ed7821c815cbf91` (its `VERSION` as written by `/sync-rules`). Copies are
  byte-identical, without `__pycache__`; nothing under `repo-standards/verify.py`,
  `repo-standards/standards/` or `.claude/skills/repo-standards/` is edited by hand.
- `repo-standards/VERSION` and `.claude/skills/repo-standards/VERSION` both contain exactly
  `b53320619b61c665f1eea27a8ed7821c815cbf91` plus a newline (same bytes as the synced copy).
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

### Task 2: This repository conforms to the standard

**Files:**
- Create: `.claude/skills/repo-standards/` (byte-identical copy of the synced workspace skill, with `VERSION`)
- Create: `.github/workflows/ci.yml` (jobs `verify`, `gitleaks`, `required`)
- Create: `.github/workflows/standards.yml` (the hub template, pinned to the Task 1 commit, comment `# set by /sync-repos`)
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
