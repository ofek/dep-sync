# SPDX-FileCopyrightText: 2024-present Ofek Lev <oss@ofek.dev>
#
# SPDX-License-Identifier: MIT
from __future__ import annotations

import os
import subprocess
import sys
from ast import literal_eval
from functools import cached_property
from typing import TypedDict

import pytest

from dep_sync.scripts import PYTHON_INFO_SCRIPT


class PythonInfo(TypedDict):
    sys_path: list[str]
    environment: dict[str, str]


@pytest.fixture
def venv(tmp_path) -> VirtualEnv:
    venv = VirtualEnv(tmp_path / "venv")
    venv.create()
    return venv


@pytest.fixture
def pip_venv(tmp_path) -> VirtualEnv:
    venv = PipVirtualEnv(tmp_path / "venv")
    venv.create()
    return venv


class VirtualEnv:
    def __init__(self, path: os.PathLike) -> None:
        self.__path = path

    def create_base_command(self) -> list[str]:
        return ["uv", "venv", "--python", sys.executable]

    def install_base_command(self) -> list[str]:
        return ["uv", "pip", "install", "--python", self.python_path]

    def create(self) -> None:
        subprocess.run([*self.create_base_command(), str(self.__path)], check=True)

    def install(self, dependencies: list[str]) -> None:
        subprocess.run([*self.install_base_command(), *dependencies], check=True)

    @cached_property
    def python_path(self) -> str:
        on_windows = sys.platform == "win32"
        return os.path.join(self.__path, "Scripts" if on_windows else "bin", "python.exe" if on_windows else "python")

    @cached_property
    def python_info(self) -> PythonInfo:
        process = subprocess.run(
            [self.python_path, "-c", PYTHON_INFO_SCRIPT], check=True, capture_output=True, text=True
        )
        return literal_eval(process.stdout)


class PipVirtualEnv(VirtualEnv):
    def create_base_command(self) -> list[str]:
        return [*super().create_base_command(), "--seed"]

    def install_base_command(self) -> list[str]:
        return [self.python_path, "-m", "pip", "install"]
