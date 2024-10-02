# SPDX-FileCopyrightText: 2024-present Ofek Lev <oss@ofek.dev>
#
# SPDX-License-Identifier: MIT
from __future__ import annotations

from functools import cached_property

from packaging.requirements import Requirement

from dep_sync._utils import path_from_url


class Dependency(Requirement):
    """
    A [`packaging.requirements.Requirement`][] with support for editable metadata.

    Parameters:
        requirement_string: The requirement string.
        editable: Whether the dependency should be editable.
    """

    def __init__(self, requirement_string: str, *, editable: bool = False) -> None:
        super().__init__(requirement_string)

        self.editable = False if self.url is None else editable

    @cached_property
    def path(self) -> str | None:
        """
        Returns:
            The path of the dependency if it's a local path, otherwise `None`.
        """
        if self.url is None:
            return None

        return path_from_url(self.url)
