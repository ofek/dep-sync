# SPDX-FileCopyrightText: 2024-present Ofek Lev <oss@ofek.dev>
#
# SPDX-License-Identifier: MIT
from __future__ import annotations

import os
import sys


def path_from_url(url: str) -> str | None:
    from urllib.parse import urlsplit

    uri = urlsplit(url)
    if uri.scheme != "file":
        return None

    return __normalize_path(uri.path)


if sys.platform == "win32":

    def __normalize_path(path: str) -> str:
        return os.path.normpath(path[1:])
else:

    def __normalize_path(path: str) -> str:
        return path
