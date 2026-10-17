"""Workflow and repository checks (spec §3.2, §3.3). A line parser, not a YAML parser: it models the
block-style workflows Pipepath writes. Anything it cannot model is a FAIL (the check gates every repo, so it
fails closed) unless the exact `<workflow file>/<job>` key is listed in `.github/standards-allow.yml`.

Threat model: a conformance check. It catches drift and honest mistakes by trusted members and agents; it is
not an adversarial boundary (a repo author can delete the workflow). Where a guarantee matters, it is made
structural: the central reusable workflow runs gitleaks itself, and the commands this module accepts for the
gitleaks scan and the `required` aggregate are exact allowlists of canonical forms, not denylists."""

import re
from pathlib import Path

CANONICAL_RUNS_ON = (
    "${{ fromJSON(((github.event_name != 'pull_request' || github.event.pull_request.head.repo.full_name"
    " == github.repository) && github.actor != 'dependabot[bot]' && vars.PIPEPATH_RUNNER) || '\"ubuntu-24.04\"') }}"
)
GITLEAKS_IMAGE = re.compile(r"ghcr\.io/gitleaks/gitleaks:v[\d.]+@sha256:[0-9a-f]{64}")
# The only accepted local gitleaks command: a single line, nothing else in the step.
GITLEAKS_EXACT = re.compile(
    r'docker run --rm -v "\$PWD:/repo" ghcr\.io/gitleaks/gitleaks:v\d+\.\d+\.\d+@sha256:[0-9a-f]{64} git /repo'
    r"( --redact)?( --verbose)?( --config [\w./-]+)?")
CENTRAL_WORKFLOW = re.compile(r"^pipepath/\.github/\.github/workflows/repo-standards\.yml@[0-9a-f]{40}$")
PR_HEADINGS = ["## Qué cambia", "## Cómo se probó", "## Spec"]
VERSION_FILE = ".claude/skills/repo-standards/VERSION"

JOB_KEY = re.compile(r"""^(?:'([^']*)'|"([^"]*)"|([\w.-]+)):(?:\s+(.*))?$""")
KEY_VALUE = re.compile(r"^([\w.-]+):(?:\s+(.*))?$")
TOP_KEY = re.compile(r"""^['"]?([\w.-]+)['"]?\s*:(.*)$""")
BLOCK_SCALAR = re.compile(r"^[|>](?:[+-]\d?|\d[+-]?)?$")
ALIAS_VALUE = re.compile(r"^[&*][A-Za-z_][\w-]*(?:\s|$)")
JOBS_KEY = re.compile(r"""^['"]?jobs['"]?\s*:(.*)$""")
# A quoted spelling of a key this checker relies on: YAML-equal to the plain key, invisible to KEY_VALUE.
QUOTED_KEY = re.compile(r"""^['"](?:uses|run|runs-on|needs|continue-on-error|if|steps|with|shell|strategy|env|secrets)['"]\s*:""")

JOB_SAFE_IF = {"always()", "success()", "true"}
NOT_SET = {"", "false"}
RESULT_VAR = re.compile(r"^\$\{\{\s*needs\.([\w-]+)\.result\s*\}\}$")
# `required` check step, canonical form 1: one expression over all needed results.
REQ_CONTAINS = ("if [ \"${{ contains(needs.*.result, 'failure') || contains(needs.*.result, 'cancelled') "
                "|| contains(needs.*.result, 'skipped') }}\" = \"true\" ]; then")
REQ_ECHO = re.compile(r'echo "(?!.*\$\()[^"`\\]*"( >&2)?')
REQ_ENV_LINE = re.compile(r'if \[ "\$(\w+)" = "pull_request" \] \|\| \[ "\$(\w+)" = "push" \]; then')
REQ_ALL_OK = re.compile(r'if (\[ "\$\w+" = "success" \](?: && \[ "\$\w+" = "success" \])*); then ok=true; fi')


def strip_comment(text):
    """Drop a trailing YAML comment (` # ...`) that is outside quotes."""
    quote = None
    for i, ch in enumerate(text):
        if quote:
            quote = None if ch == quote else quote
        elif ch in "'\"":
            quote = ch
        elif ch == "#" and (i == 0 or text[i - 1].isspace()):
            return text[:i].rstrip()
    return text.rstrip()


def unquote(v):
    if len(v) >= 2 and v[0] == v[-1] == "'":
        return v[1:-1].replace("''", "'")
    if len(v) >= 2 and v[0] == v[-1] == '"':
        return v[1:-1].replace('\\"', '"')
    return v


def _value(line):
    return line.split(":", 1)[1].strip()


def _new_job():
    return {"runs_on": None, "uses": [], "steps": [], "needs": [], "unparsed": False, "job_uses": None,
            "reason": "", "continue_on_error": None, "if": None, "strategy": False,
            "keys": set(), "timeouts": [], "dups": [], "flow": []}


def _new_step():
    return {"run": None, "run_block": False, "uses": None, "continue_on_error": None, "if": None, "shell": None,
            "fetch0": False, "env": {}, "env_flow": False, "dups": [], "keys": set()}


def _flag(job, reason):
    job["unparsed"] = True
    job["reason"] = job["reason"] or reason


def _list(val):
    return [unquote(n.strip()) for n in strip_comment(val).strip("[]").split(",") if n.strip()]


def _expr(raw):
    """Normalize a scalar that may be wrapped in `${{ }}`."""
    v = unquote(strip_comment(raw or "").strip()).strip()
    if v.startswith("${{") and v.endswith("}}"):
        v = v[3:-2].strip()
    return v.lower() if v.lower() in ("true", "false") else v


def _is_set(raw):
    """True unless the value is absent or a literal false (an expression may be true: treat it as set)."""
    return raw is not None and _expr(raw) not in NOT_SET


def _flow_map(val):
    """Parse a one-line flow mapping `{k: v, ...}` into a dict, or None if it is not plainly one."""
    val = strip_comment(val).strip()
    if len(val) < 2 or val[0] != "{" or val[-1] != "}":
        return None
    items, buf, quote, depth = [], "", None, 0
    for ch in val[1:-1]:
        if quote:
            quote = None if ch == quote else quote
        elif ch in "'\"":
            quote = ch
        elif ch in "{[":
            depth += 1
        elif ch in "}]":
            depth -= 1
        elif ch == "," and depth == 0:
            items.append(buf)
            buf = ""
            continue
        buf += ch
    if quote or depth:
        return None
    if buf.strip():
        items.append(buf)
    out = {}
    for item in items:
        if ":" not in item:
            return None
        k, v = item.split(":", 1)
        k = unquote(k.strip())
        if not k or k in out:
            return None
        out[k] = unquote(v.strip())
    return out


def has_jobs_key(text):
    return any(JOBS_KEY.match(line.strip()) for line in text.replace("\r\n", "\n").split("\n")
               if line.strip() and not line.lstrip().startswith("#"))


def _filter_values(val):
    val = strip_comment(val).strip()
    if val.startswith("["):
        return _list(val)
    return [unquote(val)] if val else []


def parse_workflow(text):
    """Return {jobs, notes, on, on_unmodeled, defaults_shell, env_keys}; notes are lines the parser could not model."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    contentful = [len(l) - len(l.lstrip(" ")) for l in lines if l.strip() and not l.lstrip().startswith("#")]
    base = min(contentful) if contentful else 0
    wf = {"jobs": {}, "notes": [], "on": None, "on_unmodeled": False, "defaults_shell": False, "env_keys": set()}
    jobs, notes = wf["jobs"], wf["notes"]
    cur, in_jobs, section, seen_content, top_keys = None, False, None, False, set()
    job_indent = prop_indent = None
    block_col, block_target, needs_open = None, None, False
    steps_open, step_indent, step, step_col, nested, nested_keys = False, None, None, None, None, set()
    on_ind = on_event = on_filter = None
    for raw in lines:
        if not raw.strip():
            continue
        indent = len(raw) - len(raw.lstrip(" ")) - base
        if block_col is not None:
            if indent > block_col:
                if block_target is not None:
                    block_target.append(raw.strip())
                continue
            block_col = None
        if raw.lstrip().startswith("#"):
            continue
        line = raw.strip()
        if indent <= 0:
            cur, job_indent, prop_indent, step, steps_open, section, in_jobs = None, None, None, None, False, None, False
            if line == "---" or line.startswith("--- ") or line == "...":
                if seen_content:
                    notes.append("multi-document YAML (--- or ...) is not modeled")
                continue
            seen_content = True
            km = TOP_KEY.match(line) if indent == 0 else None
            if not km:
                notes.append("cannot model top-level line %r" % line)
                continue
            section, rest = km.group(1), strip_comment(km.group(2)).strip()
            if section in top_keys:
                notes.append("duplicate top-level key %r (parsers may pick different values)" % section)
            top_keys.add(section)
            if section == "jobs":
                in_jobs = True
                if rest:
                    notes.append("'jobs' is not a block mapping (flow mapping or alias)")
            elif section == "on":
                on_ind = on_event = on_filter = None
                wf["on"] = {}
                if rest.startswith("{") or rest.startswith("&") or rest.startswith("*"):
                    wf["on_unmodeled"] = True
                elif rest.startswith("["):
                    wf["on"] = {e: {} for e in _list(rest)}
                elif rest:
                    wf["on"] = {unquote(rest): {}}
            continue
        if not in_jobs:
            km = KEY_VALUE.match(strip_comment(line[2:].lstrip() if line.startswith("- ") else line))
            if section == "defaults" and km and km.group(1) == "shell":
                wf["defaults_shell"] = True
            elif section == "env" and km:
                wf["env_keys"].add(km.group(1))
            elif section == "on":
                if on_ind is None:
                    on_ind = indent
                if indent == on_ind:
                    on_filter = None
                    if line.startswith("- "):
                        wf["on"][unquote(strip_comment(line[2:].strip()))] = {}
                        on_event = None
                    elif km:
                        on_event = km.group(1)
                        wf["on"][on_event] = {}
                        val = (km.group(2) or "").strip()
                        if val.startswith("{"):
                            fm = _flow_map(val)
                            if fm is None:
                                wf["on_unmodeled"] = True
                            else:
                                wf["on"][on_event] = {k: _filter_values(v) for k, v in fm.items()}
                    else:
                        wf["on_unmodeled"] = True
                elif on_event is not None and indent > on_ind:
                    if line.startswith("- ") and on_filter is not None:
                        wf["on"][on_event][on_filter].append(unquote(strip_comment(line[2:].strip())))
                    elif km:
                        on_filter = km.group(1)
                        wf["on"][on_event][on_filter] = _filter_values(km.group(2) or "")
                    else:
                        wf["on_unmodeled"] = True
            continue
        if job_indent is None:
            job_indent = indent
        if indent <= job_indent:
            m = JOB_KEY.match(strip_comment(line)) if indent == job_indent else None
            if not m:
                cur, step, steps_open = None, None, False
                notes.append("cannot model line %r" % line)
                continue
            cur, prop_indent, needs_open = m.group(1) or m.group(2) or m.group(3), None, False
            step, steps_open, step_indent = None, False, None
            if cur in jobs:
                notes.append("job %r is defined twice (parsers may pick different definitions)" % cur)
            jobs[cur] = _new_job()
            if (m.group(4) or "").strip():
                _flag(jobs[cur], "job is not a block mapping (flow mapping or alias)")
            continue
        if cur is None:
            continue
        job = jobs[cur]
        if prop_indent is None:
            prop_indent = indent
        if job.get("_ro_open"):
            if indent > prop_indent:
                _flag(job, "runs-on continues on a following line (plain-scalar continuation)")
            else:
                job["_ro_open"] = False
        is_item = line.startswith("- ")
        body = line[2:].lstrip() if is_item else line
        if needs_open and is_item and not KEY_VALUE.match(body) and indent >= prop_indent:
            job["needs"].append(unquote(strip_comment(body)))
            continue
        if indent <= prop_indent and not is_item:
            needs_open = False
            steps_open, step = False, None
        key_col = indent + (len(line) - len(body))
        m = KEY_VALUE.match(strip_comment(body))
        key, val = (m.group(1), (m.group(2) or "").strip()) if m else (None, "")
        if key:
            job["keys"].add(key)
            if key == "timeout-minutes":
                job["timeouts"].append(val)
            if val[:1] in ("[", "{", "!") and not (key == "with" and _flow_map(val) is not None):
                job["flow"].append("%s: %s" % (key, val[:20]))
        new_step = False
        if is_item and steps_open:
            if step_indent is None:
                step_indent = indent
            if indent == step_indent:
                new_step = True
                step = _new_step()
                job["steps"].append(step)
                step_col, nested = key_col, None
                if not m:
                    _flag(job, "a step is not a block mapping (flow mapping, alias or quoted key)")
        at_step = step is not None and (new_step or (not is_item and indent == step_col))
        if new_step or (at_step and key):
            nested, nested_keys = None, set()
        if QUOTED_KEY.match(body):
            _flag(job, "uses a quoted spelling of a key this check relies on")
        if indent == prop_indent and not is_item and key:
            seen = job.setdefault("_seen", set())
            if key in seen:
                job["dups"].append(key)
            seen.add(key)
        if at_step and key:
            if key in step["keys"]:
                step["dups"].append(key)
            step["keys"].add(key)
        if BLOCK_SCALAR.match(val):
            block_col = key_col
            block_target = None
            if key == "run" and at_step:
                step["run"], step["run_block"] = [], True
                block_target = step["run"]
            elif key in ("if", "continue-on-error"):
                target = step if at_step else job if (indent == prop_indent and not is_item) else None
                if target is not None:
                    target["if" if key == "if" else "continue_on_error"] = "<block scalar>"
            if key == "runs-on" and indent == prop_indent:
                _flag(job, "runs-on is a block scalar")
            continue
        if ALIAS_VALUE.match(val) or ALIAS_VALUE.match(body) or body.startswith("<<:"):
            _flag(job, "uses YAML anchors or aliases")
        if key == "uses":
            raw_uses = _value(body)
            if indent == prop_indent and not is_item:
                job["job_uses"] = raw_uses
            else:
                job["uses"].append(raw_uses)
        if at_step and key:
            if key == "run":
                step["run"] = [val]
            elif key == "uses":
                step["uses"] = unquote(strip_comment(_value(body)).strip())
            elif key == "continue-on-error":
                step["continue_on_error"] = val
            elif key == "if":
                step["if"] = val
            elif key == "shell":
                step["shell"] = unquote(val)
            elif key in ("with", "env") and val == "":
                nested = key
            elif key == "with":
                flow = _flow_map(val)
                if flow is None:
                    _flag(job, "step 'with' is not a plain block or flow mapping")
                elif flow.get("fetch-depth") == "0":
                    step["fetch0"] = True
            elif key == "env":
                flow = _flow_map(val)
                step["env_flow"] = True
                if flow is not None:
                    step["env"].update(flow)
            continue
        if step is not None and nested and key and indent > step_col:
            if key in nested_keys:
                step["dups"].append("%s.%s" % (nested, key))
            nested_keys.add(key)
            if nested == "with" and key == "fetch-depth" and unquote(val) == "0":
                step["fetch0"] = True
            elif nested == "env":
                step["env"][key] = unquote(val)
            continue
        if indent == prop_indent and not is_item:
            if key == "runs-on":
                v = unquote(val)
                if v == "" or v[0] in "[{" or v[0] in "&*":
                    _flag(job, "runs-on is not a plain scalar")
                job["runs_on"] = v
                job["_ro_open"] = True
            elif key == "needs":
                if val:
                    job["needs"] = _list(val)
                else:
                    job["needs"], needs_open = [], True
            elif key == "steps":
                steps_open, step_indent, step = val == "", None, None
                if val:
                    _flag(job, "steps is not a block sequence")
            elif key == "continue-on-error":
                job["continue_on_error"] = val
            elif key == "if":
                job["if"] = val
            elif key == "strategy":
                job["strategy"] = True
    for job in jobs.values():
        job.pop("_seen", None)
        job.pop("_ro_open", None)
    return wf


def parse(text):
    wf = parse_workflow(text)
    return wf["jobs"], wf["notes"]


def parse_jobs(text):
    return parse(text)[0]


def load_allow(root):
    path = Path(root) / ".github/standards-allow.yml"
    allow = {}
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and ":" in line:
                key, reason = line.split(":", 1)
                if reason.strip():
                    allow[key.strip()] = reason.strip()
    return allow


def _pin_problem(ref):
    ref = ref.strip()
    base = strip_comment(ref)
    if base.startswith("./") or re.match(r"^docker://[^@\s]+@sha256:[0-9a-f]{64}$", base):
        return None
    if not re.match(r"^[^@\s]+@[0-9a-f]{40}$", base):
        return "pin by 40-hex SHA"
    if not ref[len(base):].strip().lstrip("#").strip():
        return "missing version comment after the SHA"
    return None


def _read(path, rel, check, report, level="WARN"):
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        report.add(check, level, rel, "cannot read file (%s); it cannot be verified" % type(e).__name__
                   if level == "FAIL" else "cannot read file (%s); check it by hand" % type(e).__name__)
        return None


def _trigger_problem(wf):
    """Why this workflow would not run on every pull request and on push to main, or None."""
    if wf["on"] is None or wf["on_unmodeled"]:
        return "cannot model `on:`; write it in block style (pull_request, and push with branches: [main])"
    on = wf["on"]
    if "pull_request" not in on:
        return "must trigger on `pull_request`"
    if on["pull_request"]:
        return "`pull_request` must have no filters (found %s)" % ", ".join(sorted(on["pull_request"]))
    if "push" not in on:
        return "must trigger on `push` to main"
    push = on["push"]
    extra = sorted(set(push) - {"branches"})
    if extra:
        return "`push` may only filter `branches: [main]` (found %s)" % ", ".join(extra)
    if push and push.get("branches") != ["main"]:
        return "`push` must be unfiltered or `branches: [main]`"
    return None


def _workflow_problem(wf):
    if wf["defaults_shell"]:
        return "the workflow sets `defaults.run.shell`"
    bad = sorted(k for k in wf["env_keys"] if re.match(r"^(DOCKER_|BASH_ENV$|ENV$|PATH$|LD_)", k))
    if bad:
        return "the workflow sets %s in `env:`, which can redirect the scan" % ", ".join(bad)
    return None


def _job_hazards(job, strict=False):
    """Job properties that can skip or soften any job this check relies on."""
    if (job["continue_on_error"] is not None) if strict else _is_set(job["continue_on_error"]):
        return "the job has continue-on-error"
    if job["strategy"]:
        return "the job uses a strategy matrix, which this check cannot model"
    if job["keys"] & {"shell", "working-directory"}:
        return "the job sets `shell:` or `working-directory:` (anywhere in the job)"
    if any(_expr(t) in ("0", "") for t in job["timeouts"]):
        return "the job sets `timeout-minutes: 0`"
    return None


def _step_hazards(step, strict=False):
    if (step["continue_on_error"] is not None) if strict else _is_set(step["continue_on_error"]):
        return "a step has continue-on-error"
    if step["if"] is not None:
        return "a step has an `if:`"
    if step["shell"] is not None:
        return "a step sets `shell:`"
    return None


def _mentions_scan(step):
    return any("ghcr.io/gitleaks" in l or ("docker" in l and "gitleaks" in l.lower()) for l in (step["run"] or []))


def _gitleaks_job(job, wf_problem):
    """(valid, problem). Valid: a modeled job with checkout(s) and exactly one exact-form scan step."""
    mentions = [s for s in job["steps"] if _mentions_scan(s)]
    if not mentions:
        return False, None
    if wf_problem:
        return False, wf_problem
    if job["unparsed"]:
        return False, "cannot model the job (%s)" % job["reason"]
    for what, found in (("duplicate keys (a parser may pick a different value)", job["dups"]),
                        ("a YAML construct this check does not model (%s)" % ", ".join(job["flow"]), job["flow"]),
                        ("duplicate keys in a step", [d for s in job["steps"] for d in s["dups"]])):
        if found:
            return False, "the job has " + what
    if job["if"] is not None:
        return False, "the gitleaks job must not have an `if:`"
    problem = _job_hazards(job, strict=True)
    if problem:
        return False, problem
    if "env" in job["keys"]:
        return False, "the gitleaks job must not set `env:`"
    scans, checkout_seen, full = 0, False, False
    for step in job["steps"]:
        is_scan = _mentions_scan(step)
        if is_scan:
            if step["run_block"] or len(step["run"]) != 1 or not GITLEAKS_EXACT.fullmatch(step["run"][0]):
                return False, ("the scan step must be exactly one line: docker run --rm -v \"$PWD:/repo\" "
                               "ghcr.io/gitleaks/gitleaks:vX.Y.Z@sha256:<digest> git /repo [--redact] [--verbose] "
                               "[--config <path>]")
            problem = _step_hazards(step, strict=True)
            if problem:
                return False, problem
            if step["env"] or step["env_flow"]:
                return False, "the scan step must not set `env:`"
            if not full:
                return False, "gitleaks job must check out the full history (fetch-depth: 0) before the scan"
            scans += 1
        elif step["uses"] and step["uses"].startswith("actions/checkout@") and step["run"] is None:
            checkout_seen = True
            full = full or step["fetch0"]
        else:
            return False, ("the gitleaks job may only contain actions/checkout steps and the scan step "
                           "(found another step)")
    if scans != 1 or not checkout_seen:
        return False, "the gitleaks job must have a checkout step and exactly one scan step"
    return True, None


def _needs_vars(step, needs):
    """Env var -> need id for `${{ needs.X.result }}` values, or None if the set differs from `needs`."""
    out = {}
    for var, value in step["env"].items():
        m = RESULT_VAR.match(value.strip())
        if m:
            out[var] = m.group(1)
    return out if sorted(out.values()) == sorted(needs) else None


def _canonical_required_step(step, job):
    """True when the step's `run:` is one of the two canonical forms (exact lines, nothing else)."""
    if not step["run_block"] or _step_hazards(step) or step["env_flow"] or step["dups"]:
        return False
    lines = step["run"]
    if lines[:1] == [REQ_CONTAINS]:
        rest = lines[1:]
        if rest and REQ_ECHO.fullmatch(rest[0]):
            rest = rest[1:]
        return rest == ["exit 1", "fi"] and not step["env"]
    # Form 2 (spawn-control): per-need env vars, an `ok` flag, and a final `exit 1` unless every need succeeded.
    vars_ = _needs_vars(step, job["needs"])
    if not vars_ or not lines or not REQ_ECHO.fullmatch(lines[0]):
        return False
    event_vars = [v for v, val in step["env"].items() if val.strip() == "${{ github.event_name }}"]
    if len(event_vars) != 1 or len(step["env"]) != len(vars_) + 1:
        return False
    ev = event_vars[0]
    m_all = REQ_ALL_OK.fullmatch(lines[3]) if len(lines) == 9 else None
    conj_vars = re.findall(r'\$(\w+)', m_all.group(1)) if m_all else []
    return (len(lines) == 9 and lines[1] == "ok=false"
            and lines[2] == 'if [ "$%s" = "pull_request" ] || [ "$%s" = "push" ]; then' % (ev, ev)
            and sorted(conj_vars) == sorted(vars_) and lines[4] == "fi"
            and lines[5] == 'if [ "$ok" != "true" ]; then' and REQ_ECHO.fullmatch(lines[6])
            and lines[7] == "exit 1" and lines[8] == "fi")


def _required_problem(job):
    problem = _job_hazards(job)
    if problem:
        return problem
    cond = None if job["if"] is None else _expr(job["if"])
    if cond is None or cond in JOB_SAFE_IF - {"always()"}:
        return None  # GitHub skips the job (the check fails) when a need fails
    if cond not in ("always()", "!cancelled()", "failure()"):
        return "the job has an `if:` that can skip it (only none, always(), !cancelled() or failure())"
    if any(_canonical_required_step(s, job) for s in job["steps"]):
        return None
    return ("with `if: %s` the job runs even when a needed job failed, so it needs a step that fails then: use "
            "the canonical `if [ \"${{ contains(needs.*.result, 'failure') || contains(needs.*.result, 'cancelled') "
            "|| contains(needs.*.result, 'skipped') }}\" = \"true\" ]; then ...; exit 1; fi` block, or remove the `if:`"
            % cond)


def _needs_problems(jobs):
    out = []
    for job_id, job in jobs.items():
        for n in job["needs"]:
            if n == job_id:
                out.append("job %s needs itself" % job_id)
            elif n not in jobs:
                out.append("job %s needs unknown job %s" % (job_id, n))
    color = {}

    def visit(j, trail):
        color[j] = 1
        for n in jobs[j]["needs"]:
            if n in jobs and n != j:
                if color.get(n) == 1:
                    out.append("needs cycle: %s" % " -> ".join(trail + [j, n]))
                elif n not in color:
                    visit(n, trail + [j])
        color[j] = 2

    for j in jobs:
        if j not in color:
            visit(j, [])
    return out


def _caller_problem(wf):
    """None when standards.yml is a conforming caller of the central workflow, else why not."""
    callers = [(i, j) for i, j in wf["jobs"].items() if j["job_uses"]]
    good = [(i, j) for i, j in callers if CENTRAL_WORKFLOW.match(strip_comment(j["job_uses"]).strip())
            and not _pin_problem(j["job_uses"]) and not j["unparsed"] and j["if"] is None
            and not _is_set(j["continue_on_error"]) and not j["dups"]]
    if not good:
        return ("no job calls pipepath/.github/.github/workflows/repo-standards.yml pinned by a 40-hex SHA with a "
                "version comment (without `if:` or continue-on-error)")
    if any("secrets" in j["keys"] for _, j in callers):
        return "the caller job must not pass `secrets:` (including `secrets: inherit`) to the central workflow"
    return _trigger_problem(wf)


def _public_runs_on_problem(job):
    """Public mode: only the canonical expression is acceptable; it falls back to hosted runners when
    PIPEPATH_RUNNER is unset, which infra guarantees for public repositories. Nothing else may be
    credited, not even an allowlisted job or one that cannot be modeled."""
    if not job["unparsed"] and job["runs_on"] == CANONICAL_RUNS_ON:
        return None
    return "public repositories must never reach the self-hosted runners: runs-on must be exactly the canonical expression"


def _public_call_ok(job_uses):
    ref = unquote(strip_comment(job_uses).strip())
    return bool(CENTRAL_WORKFLOW.match(ref)) or ref.startswith("./.github/workflows/")


def check_workflows(root, report, public=False):
    root = Path(root)
    wf_dir = root / ".github/workflows"
    if not wf_dir.is_dir():
        return
    try:
        allow = load_allow(root)
    except (OSError, UnicodeDecodeError) as e:
        report.add("workflow-parse", "WARN", ".github/standards-allow.yml",
                   "cannot read allowlist (%s); no exceptions applied" % type(e).__name__)
        allow = {}
    has_required, has_gitleaks, standards_covers = False, False, False
    gitleaks_problems = []
    # GitHub runs only top-level *.yml / *.yaml files; anything else must not be credited.
    files = sorted(p for p in wf_dir.iterdir() if p.suffix in (".yml", ".yaml") and not p.is_dir())
    for path in files:
        rel = str(path.relative_to(root))
        text = _read(path, rel, "workflow-parse", report, level="FAIL")
        if text is None:
            continue
        wf = parse_workflow(text)
        jobs, notes = wf["jobs"], wf["notes"]
        for note in notes:
            report.add("workflow-parse", "FAIL", rel, "%s; rewrite it in block style (it cannot be allowlisted)" % note)
        if not jobs and has_jobs_key(text):
            report.add("workflow-parse", "FAIL", rel,
                       "found 'jobs:' but could not parse any job; rewrite the file in block style")
        for msg in _needs_problems(jobs):
            report.add("workflow-parse", "FAIL", rel, "%s (GitHub rejects the workflow, so none of it runs)" % msg)
        if path.name == "standards.yml":
            problem = _caller_problem(wf)
            if problem:
                report.add("standards-workflow", "FAIL", rel, problem)
            else:
                standards_covers = True
        trig = _trigger_problem(wf)
        wf_problem = trig or _workflow_problem(wf)
        for job_id, job in jobs.items():
            key = "%s/%s" % (path.name, job_id)
            for d in job["dups"] + [d for s in job["steps"] for d in s["dups"]]:
                report.add("workflow-parse", "FAIL", rel, "%s: duplicate key '%s' (parsers may pick different "
                           "values); keep one" % (job_id, d))
            if job["job_uses"]:
                problem = _pin_problem(job["job_uses"])
                if problem:
                    report.add("pinned-actions", "FAIL", rel, "%s calls a reusable workflow: %s" % (job_id, problem))
                if public and not _public_call_ok(job["job_uses"]):
                    report.add("runs-on", "FAIL", rel, "%s: public repositories must never reach the self-hosted "
                               "runners: a called reusable workflow chooses its own runners, so only the central "
                               "workflow or a local ./.github/workflows file may be called" % job_id)
                continue
            if public:
                public_problem = _public_runs_on_problem(job)
                if public_problem:
                    report.add("runs-on", "FAIL", rel, "%s: %s" % (job_id, public_problem))
            if job["unparsed"]:
                reason = "cannot model this job (%s)" % job["reason"]
            elif job["runs_on"] != CANONICAL_RUNS_ON:
                reason = ("runs-on uses a matrix expression, which cannot be modeled" if "matrix." in (job["runs_on"] or "")
                          else None)
            else:
                reason = None
            if public and _public_runs_on_problem(job):
                pass  # already reported above; the allowlist never applies to runs-on in public mode
            elif reason and key not in allow:
                report.add("runs-on", "FAIL", rel, "%s: %s; rewrite it in block style or list '%s' in "
                           ".github/standards-allow.yml with a reason" % (job_id, reason, key))
            elif job["runs_on"] != CANONICAL_RUNS_ON and not reason and not job["unparsed"] and key not in allow:
                report.add("runs-on", "FAIL", rel, "%s does not use the canonical runs-on" % job_id)
            for ref in job["uses"]:
                problem = _pin_problem(ref)
                if problem:
                    report.add("pinned-actions", "FAIL", rel, "%s uses %s (%s)" % (job_id, ref, problem))
            valid, problem = _gitleaks_job(job, wf_problem)
            if valid:
                has_gitleaks = True
            elif problem:
                gitleaks_problems.append((rel, job_id, problem))
            if job_id == "required":
                if job["unparsed"]:
                    pass  # already a runs-on FAIL unless allowlisted; an unmodeled aggregate is never credited
                else:
                    problem = _required_problem(job)
                    if problem:
                        report.add("required-job", "FAIL", rel, "'required' is not a reliable aggregate: %s" % problem)
                    else:
                        has_required = True
        req = jobs.get("required")
        if req and not req["unparsed"]:
            missing = [j for j in jobs if j != "required" and j not in req["needs"]]
            if missing:
                report.add("required-job", "FAIL", rel, "'required' must need every other job; missing: %s"
                           % ", ".join(missing))
    if not has_required:
        report.add("required-job", "FAIL", ".github/workflows",
                   "no usable job named 'required' (it must exist, be modelable, and either have no `if:` or "
                   "run the canonical check of the needed results)")
    if not (has_gitleaks or standards_covers):
        report.add("gitleaks", "FAIL", ".github/workflows",
                   "gitleaks is not covered: either keep a valid `.github/workflows/standards.yml` (the central "
                   "workflow runs gitleaks over the full history) or add a local job whose scan step is exactly "
                   "`docker run --rm -v \"$PWD:/repo\" ghcr.io/gitleaks/gitleaks:vX.Y.Z@sha256:<digest> git /repo`")
        for rel, job_id, problem in gitleaks_problems:
            report.add("gitleaks", "FAIL", rel, "%s: %s" % (job_id, problem))


def check_pr_template(root, report):
    rel = ".github/pull_request_template.md"
    path = Path(root) / rel
    if not path.is_file():
        return
    text = _read(path, rel, "pr-template", report)
    if text is None:
        return
    lines = [l.strip() for l in text.splitlines()]
    for h in PR_HEADINGS:
        if h not in lines:
            report.add("pr-template", "FAIL", rel, "missing heading '%s'" % h)


def check_skill_version(root, report, version):
    if not version:
        return
    path = Path(root) / VERSION_FILE
    have = None
    if path.is_file():
        text = _read(path, VERSION_FILE, "skill-version", report)
        if text is None:
            return
        have = text.strip()
    if have != version:
        report.add("skill-version", "FAIL", VERSION_FILE,
                   "copy is %s, central check is %s; run /sync-repos" % (have or "missing", version))
