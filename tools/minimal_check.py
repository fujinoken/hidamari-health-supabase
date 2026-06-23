from __future__ import annotations

import ast
import importlib
import re
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SYNTAX_TARGETS = [
    PROJECT_ROOT / "app.py",
    PROJECT_ROOT / "db" / "database.py",
]

IMPORT_NAME_OVERRIDES = {
    "opencv-python": "cv2",
    "pillow": "PIL",
    "python-dotenv": "dotenv",
    "pyyaml": "yaml",
}


def check_syntax(path: Path) -> tuple[bool, str]:
    try:
        source = path.read_text(encoding="utf-8")
        ast.parse(source, filename=str(path))
        return True, "OK"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def requirement_to_import_name(line: str) -> str:
    name = re.split(r"[<>=!~;\[]", line.strip(), maxsplit=1)[0].strip()
    normalized = name.lower().replace("_", "-")
    return IMPORT_NAME_OVERRIDES.get(normalized, name.replace("-", "_"))


def iter_requirement_imports(path: Path) -> list[str]:
    imports: list[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        imports.append(requirement_to_import_name(line))
    return imports


def check_import(module_name: str) -> tuple[bool, str]:
    try:
        importlib.import_module(module_name)
        return True, "OK"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def main() -> int:
    failures: list[str] = []

    print("Syntax checks")
    for path in SYNTAX_TARGETS:
        ok, message = check_syntax(path)
        rel = path.relative_to(PROJECT_ROOT)
        print(f"- {rel}: {message}")
        if not ok:
            failures.append(f"syntax:{rel}")

    print("\nRequirement import checks")
    requirements_path = PROJECT_ROOT / "requirements.txt"
    for module_name in iter_requirement_imports(requirements_path):
        ok, message = check_import(module_name)
        print(f"- {module_name}: {message}")
        if not ok:
            failures.append(f"import:{module_name}")

    if failures:
        print("\nFAILED")
        return 1

    print("\nOK")
    return 0


if __name__ == "__main__":
    sys.exit(main())

