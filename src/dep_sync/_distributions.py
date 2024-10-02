# SPDX-FileCopyrightText: 2024-present Ofek Lev <oss@ofek.dev>
#
# SPDX-License-Identifier: MIT
from __future__ import annotations

import re
import sys
from importlib.metadata import Distribution, DistributionFinder

from packaging.markers import default_environment

from dep_sync._dependency import Dependency
from dep_sync._utils import path_from_url


class DependencyState:
    """
    Represents the state of dependencies within a Python environment as returned by the
    [`dep_sync.InstalledDistributions.dependency_state`][] method.
    """

    __slots__ = ("missing", "not_required", "satisfied")

    def __init__(self, *, satisfied: list[Dependency], missing: list[Dependency], not_required: list[str]) -> None:
        self.satisfied = tuple(satisfied)
        self.missing = tuple(missing)
        self.not_required = tuple(not_required)


class InstalledDistributions:
    """
    Represents the installed distributions within a Python environment. This adds caching to the distribution
    discovery process for improved performance and should be used instead of the standalone functions when the
    state of the environment would not change between calls.

    Parameters:
        sys_path: The list of directories to search for installed distributions, defaulting to [`sys.path`][].
        environment: The marker environment, defaulting to [`packaging.markers.default_environment`][].
    """

    def __init__(self, *, sys_path: list[str] | None = None, environment: dict[str, str] | None = None) -> None:
        self.__sys_path: list[str] = sys.path if sys_path is None else sys_path
        self.__environment: dict[str, str] = (
            default_environment() if environment is None else environment  # type: ignore[assignment]
        )
        self.__resolver = Distribution.discover(context=DistributionFinder.Context(path=self.__sys_path))
        self.__distributions: dict[str, Distribution] = {}
        self.__search_exhausted = False
        self.__canonical_regex = re.compile(r"[-_.]+")

    def dependencies_satisfied(self, dependencies: list[Dependency]) -> bool:
        """
        This should be preferred for simple checks as the discovery process halts when a dependency is not satisfied.

        Parameters:
            dependencies: The dependencies to check.

        Returns:
            Whether all the dependencies are satisfied.
        """
        return all(self.__satisfied(dependency) for dependency in dependencies)

    def dependency_state(self, dependencies: list[Dependency], *, exhaustive: bool = False) -> DependencyState:
        """
        This should be preferred for more complex checks as it returns the state of all dependencies. If the
        `exhaustive` argument is `True`, the `not_required` attribute of the returned [`dep_sync.DependencyState`][]
        will contain the names of all distributions found in the environment that were not requested. If not,
        the attribute will be empty.

        Parameters:
            dependencies: The dependencies to check.
            exhaustive: Whether to search for all distributions that are not required.

        Returns:
            An instance of [`dep_sync.DependencyState`][].
        """
        satisfied: list[Dependency] = []
        missing: list[Dependency] = []
        not_required: list[str] = []
        names: set[str] = set()
        for dependency in dependencies:
            names.add(self.__normalize_name(dependency.name))
            if self.__satisfied(dependency):
                satisfied.append(dependency)
            else:
                missing.append(dependency)

        if exhaustive:
            if not self.__search_exhausted:
                for distribution in self.__resolver:
                    name = distribution.metadata["Name"]
                    if name is None:  # no cov
                        continue

                    name = self.__normalize_name(name)
                    self.__distributions[name] = distribution

                self.__search_exhausted = True

            not_required.extend(name for name in self.__distributions if name not in names)

        return DependencyState(satisfied=satisfied, missing=missing, not_required=not_required)

    def get(self, project_name: str) -> Distribution | None:
        """
        Parameters:
            project_name: The name of the project.

        Returns:
            The distribution for the given project name, or `None` if a distribution is not found.
        """
        project_name = self.__canonical_regex.sub("-", project_name).lower()
        possible_distribution = self.__distributions.get(project_name)
        if possible_distribution is not None:
            return possible_distribution

        if self.__search_exhausted:
            return None

        for distribution in self.__resolver:
            name = distribution.metadata["Name"]
            if name is None:  # no cov
                continue

            name = self.__normalize_name(name)
            self.__distributions[name] = distribution
            if name == project_name:
                return distribution

        self.__search_exhausted = True
        return None

    def __normalize_name(self, name: str) -> str:
        return self.__canonical_regex.sub("-", name).lower()

    def __satisfied(self, dependency: Dependency, *, environment: dict[str, str] | None = None) -> bool:
        if environment is None:
            environment = self.__environment

        if dependency.marker and not dependency.marker.evaluate(environment):
            return True

        distribution = self.get(dependency.name)
        if distribution is None:
            return False

        extras = dependency.extras
        if extras:
            transitive_dependencies: list[str] = distribution.metadata.get_all("Requires-Dist", [])
            if not transitive_dependencies:
                return False

            available_extras: list[str] = distribution.metadata.get_all("Provides-Extra", [])

            for dependency_string in transitive_dependencies:
                transitive_dependency = Dependency(dependency_string)
                if not transitive_dependency.marker:
                    continue

                for extra in extras:
                    # FIXME: This may cause a build to never be ready if newer versions do not provide the desired
                    # extra and it's just a user error/typo. See: https://github.com/pypa/pip/issues/7122
                    if extra not in available_extras:
                        return False

                    extra_environment = dict(environment)
                    extra_environment["extra"] = extra
                    if not self.__satisfied(transitive_dependency, environment=extra_environment):
                        return False

        if dependency.specifier and not dependency.specifier.contains(distribution.version):
            return False

        if not dependency.url:
            return True

        # TODO: handle https://discuss.python.org/t/11938
        direct_url_file = distribution.read_text("direct_url.json")
        if direct_url_file is None:
            return False

        import json

        # https://packaging.python.org/specifications/direct-url/
        direct_url_data = json.loads(direct_url_file)
        url = direct_url_data["url"]
        if "dir_info" in direct_url_data:
            dir_info = direct_url_data["dir_info"]
            editable = dir_info.get("editable", False)
            if editable != dependency.editable:
                return False

            if path_from_url(url) != dependency.path:
                return False
        elif "vcs_info" in direct_url_data:
            vcs_info = direct_url_data["vcs_info"]
            vcs = vcs_info["vcs"]
            commit_id = vcs_info["commit_id"]
            requested_revision = vcs_info.get("requested_revision")

            # Try a few variations, see https://peps.python.org/pep-0440/#direct-references
            if (
                requested_revision and dependency.url == f"{vcs}+{url}@{requested_revision}#{commit_id}"
            ) or dependency.url == f"{vcs}+{url}@{commit_id}":
                return True

            if dependency.url in {f"{vcs}+{url}", f"{vcs}+{url}@{requested_revision}"}:
                import subprocess

                if vcs == "git":
                    vcs_cmd = [vcs, "ls-remote", url]
                    if requested_revision:
                        vcs_cmd.append(requested_revision)
                # TODO: support other VCS
                else:  # no cov
                    return False

                result = subprocess.run(vcs_cmd, capture_output=True, text=True)  # noqa: PLW1510
                if result.returncode or not result.stdout.strip():
                    return False

                latest_commit_id, *_ = result.stdout.split()
                return commit_id == latest_commit_id

            return False

        return url == dependency.url


def dependencies_satisfied(
    dependencies: list[Dependency], *, sys_path: list[str] | None = None, environment: dict[str, str] | None = None
) -> bool:
    """
    This is equivalent to creating an instance of [`InstalledDistributions`][dep_sync.InstalledDistributions] and
    calling its [`dependencies_satisfied`][dep_sync.InstalledDistributions.dependencies_satisfied] method.

    Parameters:
        dependencies: The dependencies to check.
        sys_path: The list of directories to search for installed distributions, defaulting to [`sys.path`][].
        environment: The marker environment, defaulting to [`packaging.markers.default_environment`][].

    Returns:
        Whether all the dependencies are satisfied.
    """
    distributions = InstalledDistributions(sys_path=sys_path, environment=environment)
    return distributions.dependencies_satisfied(dependencies)


def dependency_state(
    dependencies: list[Dependency],
    *,
    exhaustive: bool = False,
    sys_path: list[str] | None = None,
    environment: dict[str, str] | None = None,
) -> DependencyState:
    """
    This is equivalent to creating an instance of [`InstalledDistributions`][dep_sync.InstalledDistributions] and
    calling its [`dependency_state`][dep_sync.InstalledDistributions.dependency_state] method.

    Parameters:
        dependencies: The dependencies to check.
        exhaustive: Whether to search for all distributions that are not required.

    Returns:
        An instance of [`dep_sync.DependencyState`][].
    """
    distributions = InstalledDistributions(sys_path=sys_path, environment=environment)
    return distributions.dependency_state(dependencies, exhaustive=exhaustive)
