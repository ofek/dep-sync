# SPDX-FileCopyrightText: 2024-present Ofek Lev <oss@ofek.dev>
#
# SPDX-License-Identifier: MIT
from __future__ import annotations

import shutil
from pathlib import Path

from dep_sync import Dependency, InstalledDistributions, dependencies_satisfied, dependency_state


def test_no_dependencies(venv):
    deps = []
    assert dependencies_satisfied(deps, sys_path=venv.python_info["sys_path"])

    state = dependency_state(deps, sys_path=venv.python_info["sys_path"])
    assert not state.satisfied
    assert not state.missing
    assert not state.not_required


def test_exhaustive_missing_dependencies(venv):
    distributions = InstalledDistributions(sys_path=venv.python_info["sys_path"])

    deps = [Dependency("binary")]
    assert not distributions.dependencies_satisfied(deps)

    state = distributions.dependency_state(deps, exhaustive=True)
    assert not state.satisfied
    assert state.missing == (deps[0],)
    assert not state.not_required


def test_exhaustive_dependencies_satisfied(venv):
    distributions = InstalledDistributions(sys_path=venv.python_info["sys_path"])
    venv.install(["binary", "urllib3"])

    deps = [Dependency("binary")]
    assert distributions.dependencies_satisfied(deps)

    state = distributions.dependency_state(deps, exhaustive=True)
    assert state.satisfied == (deps[0],)
    assert not state.missing
    assert state.not_required == ("urllib3",)


def test_missing_any_version(venv):
    distributions = InstalledDistributions(sys_path=venv.python_info["sys_path"])

    deps = [Dependency("binary")]
    assert not distributions.dependencies_satisfied(deps)

    state = distributions.dependency_state(deps)
    assert not state.satisfied
    assert state.missing == (Dependency("binary"),)


def test_satisfied_any_version(venv):
    distributions = InstalledDistributions(sys_path=venv.python_info["sys_path"])
    venv.install(["binary"])

    deps = [Dependency("binary")]
    assert distributions.dependencies_satisfied(deps)

    state = distributions.dependency_state(deps)
    assert state.satisfied == (deps[0],)
    assert not state.missing


def test_unsatisfied_version(venv):
    distributions = InstalledDistributions(sys_path=venv.python_info["sys_path"])
    venv.install(["binary"])

    deps = [Dependency("binary>9000")]
    assert not distributions.dependencies_satisfied(deps)

    state = distributions.dependency_state(deps)
    assert not state.satisfied
    assert state.missing == (deps[0],)


def test_partially_satisfied(venv):
    distributions = InstalledDistributions(sys_path=venv.python_info["sys_path"])
    venv.install(["urllib3"])

    deps = [Dependency("binary"), Dependency("urllib3")]
    assert not distributions.dependencies_satisfied(deps)

    state = distributions.dependency_state(deps)
    assert state.satisfied == (deps[1],)
    assert state.missing == (deps[0],)


def test_satisfied_marker_no_dependency(venv):
    distributions = InstalledDistributions(sys_path=venv.python_info["sys_path"])

    deps = [Dependency("binary; python_version < '1'")]
    assert distributions.dependencies_satisfied(deps)

    state = distributions.dependency_state(deps)
    assert state.satisfied == (deps[0],)
    assert not state.missing


def test_unsatisfied_marker(venv):
    distributions = InstalledDistributions(sys_path=venv.python_info["sys_path"])

    deps = [Dependency("binary; python_version > '1'")]
    assert not distributions.dependencies_satisfied(deps)

    state = distributions.dependency_state(deps)
    assert not state.satisfied
    assert state.missing == (deps[0],)


def test_extra_no_dependencies(venv):
    distributions = InstalledDistributions(sys_path=venv.python_info["sys_path"])
    venv.install(["binary"])

    deps = [Dependency("binary[foo]")]
    assert not distributions.dependencies_satisfied(deps)

    state = distributions.dependency_state(deps)
    assert not state.satisfied
    assert state.missing == (deps[0],)


def test_extra_unknown(venv):
    distributions = InstalledDistributions(sys_path=venv.python_info["sys_path"])
    venv.install(["requests[security]==2.25.1"])

    deps = [Dependency("requests[foo]")]
    assert not distributions.dependencies_satisfied(deps)

    state = distributions.dependency_state(deps)
    assert not state.satisfied
    assert state.missing == (deps[0],)


def test_extra_satisfied(venv):
    distributions = InstalledDistributions(sys_path=venv.python_info["sys_path"])
    venv.install(["requests[security]==2.25.1"])

    deps = [Dependency("requests[security]")]
    assert distributions.dependencies_satisfied(deps)

    state = distributions.dependency_state(deps)
    assert state.satisfied == (deps[0],)
    assert not state.missing


def test_extra_unsatisfied(venv):
    distributions = InstalledDistributions(sys_path=venv.python_info["sys_path"])
    venv.install(["requests==2.25.1"])

    deps = [Dependency("requests[security]")]
    assert not distributions.dependencies_satisfied(deps)

    state = distributions.dependency_state(deps)
    assert not state.satisfied
    assert state.missing == (deps[0],)


def test_git_dependency_installed_from_index(venv):
    distributions = InstalledDistributions(sys_path=venv.python_info["sys_path"])
    venv.install(["requests"])

    deps = [Dependency("requests@git+https://github.com/psf/requests")]
    assert not distributions.dependencies_satisfied(deps)

    state = distributions.dependency_state(deps)
    assert not state.satisfied
    assert state.missing == (deps[0],)


def test_git_no_revision_pip(pip_venv):
    distributions = InstalledDistributions(sys_path=pip_venv.python_info["sys_path"])
    pip_venv.install(["requests@git+https://github.com/psf/requests"])

    deps = [Dependency("requests@git+https://github.com/psf/requests")]
    assert distributions.dependencies_satisfied(deps)

    state = distributions.dependency_state(deps)
    assert state.satisfied == (deps[0],)
    assert not state.missing


def test_git_no_revision_uv(venv):
    distributions = InstalledDistributions(sys_path=venv.python_info["sys_path"])
    venv.install(["requests@git+https://github.com/psf/requests"])

    deps = [Dependency("requests@git+https://github.com/psf/requests")]
    assert not distributions.dependencies_satisfied(deps)

    state = distributions.dependency_state(deps)
    assert not state.satisfied
    assert state.missing == (deps[0],)


def test_git_revision_pip(pip_venv):
    distributions = InstalledDistributions(sys_path=pip_venv.python_info["sys_path"])
    pip_venv.install(["requests@git+https://github.com/psf/requests@main"])

    deps = [Dependency("requests@git+https://github.com/psf/requests@main")]
    assert distributions.dependencies_satisfied(deps)

    state = distributions.dependency_state(deps)
    assert state.satisfied == (deps[0],)
    assert not state.missing


def test_git_revision_uv(venv):
    distributions = InstalledDistributions(sys_path=venv.python_info["sys_path"])
    venv.install(["requests@git+https://github.com/psf/requests@main"])

    deps = [Dependency("requests@git+https://github.com/psf/requests@main")]
    assert not distributions.dependencies_satisfied(deps)

    state = distributions.dependency_state(deps)
    assert not state.satisfied
    assert state.missing == (deps[0],)


def test_git_commit(venv):
    distributions = InstalledDistributions(sys_path=venv.python_info["sys_path"])
    venv.install(["requests@git+https://github.com/psf/requests@7f694b79e114c06fac5ec06019cada5a61e5570f"])

    deps = [Dependency("requests@git+https://github.com/psf/requests@7f694b79e114c06fac5ec06019cada5a61e5570f")]
    assert distributions.dependencies_satisfied(deps)

    state = distributions.dependency_state(deps)
    assert state.satisfied == (deps[0],)
    assert not state.missing


def test_directory(venv):
    distributions = InstalledDistributions(sys_path=venv.python_info["sys_path"])
    venv.install(["."])

    deps = [Dependency(f"dep-sync@{Path.cwd().as_uri()}")]
    assert distributions.dependencies_satisfied(deps)

    state = distributions.dependency_state(deps)
    assert state.satisfied == (deps[0],)
    assert not state.missing


def test_directory_path_mismatch(venv, tmp_path):
    distributions = InstalledDistributions(sys_path=venv.python_info["sys_path"])
    project_path = tmp_path / "project"
    project_path.mkdir()
    shutil.copy(Path.cwd() / "pyproject.toml", project_path / "pyproject.toml")
    shutil.copy(Path.cwd() / "README.md", project_path / "README.md")
    shutil.copytree(Path.cwd() / "src", project_path / "src")
    shutil.copytree(Path.cwd() / ".git", project_path / ".git")
    venv.install([str(project_path)])

    deps = [Dependency(f"dep-sync@{Path.cwd().as_uri()}")]
    assert not distributions.dependencies_satisfied(deps)

    state = distributions.dependency_state(deps)
    assert not state.satisfied
    assert state.missing == (deps[0],)


def test_directory_editable(venv):
    distributions = InstalledDistributions(sys_path=venv.python_info["sys_path"])
    venv.install(["-e", "."])

    deps = [Dependency(f"dep-sync@{Path.cwd().as_uri()}", editable=True)]
    assert distributions.dependencies_satisfied(deps)

    state = distributions.dependency_state(deps)
    assert state.satisfied == (deps[0],)
    assert not state.missing


def test_directory_editable_unsatisfied(venv):
    distributions = InstalledDistributions(sys_path=venv.python_info["sys_path"])
    venv.install(["."])

    deps = [Dependency(f"dep-sync@{Path.cwd().as_uri()}", editable=True)]
    assert not distributions.dependencies_satisfied(deps)

    state = distributions.dependency_state(deps)
    assert not state.satisfied
    assert state.missing == (deps[0],)


def test_url_check_fallback(venv):
    distributions = InstalledDistributions(sys_path=venv.python_info["sys_path"])
    venv.install(["requests@https://github.com/psf/requests/archive/refs/heads/main.zip"])

    deps = [Dependency("requests@https://github.com/psf/requests/archive/refs/heads/main.zip")]
    assert distributions.dependencies_satisfied(deps)

    state = distributions.dependency_state(deps)
    assert state.satisfied == (deps[0],)
    assert not state.missing


def test_unsupported_direct_reference(venv):
    distributions = InstalledDistributions(sys_path=venv.python_info["sys_path"])
    venv.install(["requests@git+https://github.com/psf/requests"])

    deps = [Dependency("requests@git+sftp:github.com:psf/requests")]
    assert not distributions.dependencies_satisfied(deps)

    state = distributions.dependency_state(deps)
    assert not state.satisfied
    assert state.missing == (deps[0],)
