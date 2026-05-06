# Copyright 2026 UCP Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Behavioral tests for the generate_models.sh entry point.

These guard the strict-mode invariants — the script must exit nonzero
before any regen runs when given a ref that doesn't resolve, so a typo
or transient network failure can't silently leave the tree built from
the wrong upstream commit.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "generate_models.sh"


@pytest.mark.skipif(
    shutil.which("git") is None or shutil.which("uv") is None,
    reason="generate_models.sh needs git and uv on PATH",
)
def test_bad_ref_aborts_before_regen(tmp_path: Path) -> None:
    """A nonexistent ref must abort with nonzero exit, not regen on main.

    The script clones into ./ucp/ before running the codegen step; if
    the checkout silently fell back to the default branch (the regression
    mode `set -e` exists to prevent), we'd end up with a populated `ucp/`
    tree at HEAD ≠ the requested ref. We assert the script aborts and the
    output directory contains nothing beyond the in-progress clone.
    """
    bogus = "deadbeefcafe1234deadbeefcafe1234deadbeef"
    work = tmp_path / "sdk"
    shutil.copytree(
        REPO_ROOT,
        work,
        ignore=shutil.ignore_patterns(
            "ucp",
            ".venv",
            "node_modules",
            "__pycache__",
            "*.pyc",
        ),
    )

    proc = subprocess.run(
        ["bash", str(work / "generate_models.sh"), "--ref", bogus],
        cwd=work,
        capture_output=True,
        text=True,
        env={**os.environ, "PATH": os.environ.get("PATH", "")},
    )
    assert proc.returncode != 0, (
        f"expected nonzero exit, got {proc.returncode}\n"
        f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    )
    # The script must have aborted before reaching the codegen step,
    # which is the only thing that writes _schema_ref.py.
    schema_ref = work / "src" / "ucp_sdk" / "_schema_ref.py"
    assert (
        schema_ref.read_text()
        == (REPO_ROOT / "src" / "ucp_sdk" / "_schema_ref.py").read_text()
    ), (
        "_schema_ref.py was rewritten by a failed regen — "
        "the strict-mode guard didn't fire"
    )
