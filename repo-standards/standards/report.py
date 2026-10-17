"""Findings shared by the documentation and CI checks."""

import json
from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class Finding:
    check: str
    level: str  # "FAIL" or "WARN"
    path: str
    message: str


@dataclass
class Report:
    findings: list = field(default_factory=list)

    def add(self, check, level, path, message):
        assert level in ("FAIL", "WARN"), level
        self.findings.append(Finding(check, level, str(path), message))

    def exit_code(self):
        return 1 if any(f.level == "FAIL" for f in self.findings) else 0

    def to_text(self):
        if not self.findings:
            return "PASS repo-standards"
        return "\n".join("%s %s %s: %s" % (f.level, f.check, f.path, f.message) for f in self.findings)

    def to_json(self):
        return json.dumps({"findings": [asdict(f) for f in self.findings]}, ensure_ascii=False, indent=2)
