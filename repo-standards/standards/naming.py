"""Repository name check (spec §9.3). The convention itself (§9.1) is partly judgement: whether a name is the
site's host or a product's piece is reviewed by people. This module checks only the mechanical part: the form,
the org prefix, the stack-type suffixes and the workspace pairing."""

import re

from standards.ci import REPO_NAME

NAME_FORM = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
FORBIDDEN_SUFFIXES = ("-app", "-site", "-landing", "-repo")
EXEMPT_NAMES = (".github",)
HUB_NAME = "workspaces-hub"
PREFIX = "pipepath-"
PREFIX_EXCEPTION = "pipepath-workspace"


def _real_dir(path):
    return path.is_dir() and not path.is_symlink()


def _real_file(path):
    return path.is_file() and not path.is_symlink()


def check_repo_name(root, report, repo_name=None):
    if repo_name is None or REPO_NAME.fullmatch(repo_name) is None or repo_name in (".", ".."):
        report.add("repo-name", "WARN", ".", "no valid --repo-name was given, so the repository name was not checked")
        return
    if repo_name in EXEMPT_NAMES:
        return
    problems = []
    if NAME_FORM.fullmatch(repo_name) is None:
        problems.append("use lowercase letters, digits and single hyphens (^[a-z0-9]+(-[a-z0-9]+)*$)")
    if repo_name.startswith(PREFIX) and repo_name != PREFIX_EXCEPTION:
        problems.append("drop the pipepath- prefix: the organization is already the namespace")
    for suffix in FORBIDDEN_SUFFIXES:
        if repo_name.endswith(suffix):
            problems.append("drop the %s suffix: name the thing, not its stack (a site takes its host's name)"
                            % suffix)
    has_rules = _real_dir(root / "org-rules")
    if repo_name.endswith("-workspace") and not has_rules:
        problems.append("a -workspace name needs the workspace layout (an org-rules/ directory)")
    if has_rules and _real_file(root / ".gitmodules") and not repo_name.endswith("-workspace") \
            and repo_name != HUB_NAME:
        problems.append("a workspace (org-rules/ and .gitmodules) is named <scope>-workspace")
    for problem in problems:
        report.add("repo-name", "FAIL", ".", "%s: %s" % (repo_name, problem))
