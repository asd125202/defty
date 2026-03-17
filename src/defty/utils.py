# Copyright (c) 2026 APRL Technologies Inc. All rights reserved.
# Author: Yiju Li
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
"""Shared internal utilities for Defty."""

from __future__ import annotations

import logging
import subprocess
import sys
import time
from pathlib import Path

logger = logging.getLogger(__name__)

__all__ = ["spawn_rerun_detached"]


def spawn_rerun_detached(port: int = 9876) -> "subprocess.Popen | None":
    """Spawn the Rerun viewer as a fully detached process.

    The viewer is isolated from our console process group so that pressing
    Ctrl+C in the terminal does *not* send CTRL_C_EVENT / SIGINT to the
    viewer.  This prevents the Python traceback that occurs when the viewer
    is launched via ``rr.spawn()`` (which uses our process group).

    After calling this function, connect with::

        rr.init("my-session", spawn=False)
        rr.connect_grpc()   # default: rerun+http://127.0.0.1:9876/proxy

    Args:
        port: TCP port the Rerun gRPC server listens on (default 9876).

    Returns:
        The subprocess handle on success, or ``None`` if the binary cannot
        be located or the process fails to start.
    """
    try:
        import rerun as rr
    except ImportError:
        logger.warning("rerun-sdk not installed; Rerun display unavailable.")
        return None

    rust_exe = (
        Path(rr.__file__).parent.parent
        / "rerun_cli"
        / ("rerun.exe" if sys.platform == "win32" else "rerun")
    )
    if not rust_exe.exists():
        logger.warning("Rerun binary not found at %s", rust_exe)
        return None

    try:
        if sys.platform == "win32":
            proc = subprocess.Popen(
                [str(rust_exe)],
                creationflags=(
                    subprocess.CREATE_NEW_PROCESS_GROUP
                    | subprocess.DETACHED_PROCESS
                ),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            proc = subprocess.Popen(
                [str(rust_exe)],
                start_new_session=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
    except OSError as exc:
        logger.warning("Failed to spawn Rerun viewer: %s", exc)
        return None

    time.sleep(1.2)  # wait for gRPC server to be ready
    return proc
