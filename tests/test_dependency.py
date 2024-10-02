# SPDX-FileCopyrightText: 2024-present Ofek Lev <oss@ofek.dev>
#
# SPDX-License-Identifier: MIT
from __future__ import annotations

import sys

import pytest

from dep_sync import Dependency


class TestEditable:
    def test_not_url(self):
        dep = Dependency("pkg", editable=True)
        assert dep.editable is False

    def test_url_editable(self):
        dep = Dependency("pkg @ file:///a/b/c", editable=True)
        assert dep.editable is True

    def test_url_default(self):
        dep = Dependency("pkg @ file:///a/b/c")
        assert dep.editable is False


class TestPath:
    def test_not_url(self):
        dep = Dependency("pkg")
        assert dep.path is None

    def test_scheme_not_file(self):
        dep = Dependency("pkg @ git+https://foo/bar/baz.git")
        assert dep.path is None

    @pytest.mark.skipif(sys.platform != "win32", reason="Requires Windows system")
    def test_windows(self):
        dep = Dependency("pkg @ file:///C:/b/a")
        assert dep.path == "C:\\b\\a"

    @pytest.mark.skipif(sys.platform == "win32", reason="Requires non-Windows system")
    def test_unix(self):
        dep = Dependency("pkg @ file:///c/b/a")
        assert dep.path == "/c/b/a"
