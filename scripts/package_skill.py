#!/usr/bin/env python3
"""Package the Mythify skill into dist/mythify.skill.

Zips the contents of skills/mythify/ so that SKILL.md sits at the zip root
with references/ beside it. Standard library only. Prints the entry list and
an [OK] line on success; exits non-zero with a [FAIL] line on error.
"""

import sys
import zipfile
from pathlib import Path


def main():
    repo_root = Path(__file__).resolve().parent.parent
    skill_dir = repo_root / "skills" / "mythify"
    dist_dir = repo_root / "dist"
    output = dist_dir / "mythify.skill"

    if not skill_dir.is_dir():
        print("[FAIL] Skill directory not found: {}".format(skill_dir), file=sys.stderr)
        return 1

    files = sorted(
        path
        for path in skill_dir.rglob("*")
        if path.is_file() and not path.name.startswith(".")
    )
    if not any(path.name == "SKILL.md" and path.parent == skill_dir for path in files):
        print("[FAIL] SKILL.md missing from {}".format(skill_dir), file=sys.stderr)
        return 1

    dist_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            arcname = path.relative_to(skill_dir).as_posix()
            archive.write(path, arcname)
            print(arcname)

    print("[OK] Wrote {} ({} entries)".format(output, len(files)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
