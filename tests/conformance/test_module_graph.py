"""Module dependency graph conformance (01.18.1, 02.1, 21A §7–§8).

`01` states two architectural rules that nothing in this repository proved
until now, and both are properties of the *shape* of the code rather than of
any one module's behaviour — which is why no module's own suite could catch a
violation:

> No circular dependencies between modules. If detected, the architecture must
> be refactored immediately.

> No module may directly invoke another module's internal functions across
> process boundaries.

The second is what every module's `adapters.py` convention exists to serve, and
each module asserts it locally. This file asserts the global property those
local checks add up to, which is the one a single module cannot see: a cycle
needs at least two modules to exist, and every module in it looks fine on its
own.

The graph is read from import statements rather than from a maintained list.
A maintained list is a second description of the architecture, and the moment
it disagrees with the imports it is the imports that are true.
"""

from __future__ import annotations

import pathlib
import re
from collections import defaultdict

import pytest

REPO = pathlib.Path(__file__).resolve().parents[2]


#: The deployable units. Read from the filesystem so a module added without
#: being listed here is still checked — the alternative is a test that silently
#: stops covering whatever was added most recently.
def module_names() -> set[str]:
    names: set[str] = set()
    for parent in ("libs", "services"):
        for path in (REPO / parent).iterdir():
            if path.is_dir() and (path / path.name).is_dir():
                names.add(path.name)
    return names


MODULES = module_names()

_IMPORT = re.compile(r"^\s*(?:from\s+([A-Za-z_][\w.]*)|import\s+([A-Za-z_][\w.]*))")


def _package_root(module: str) -> pathlib.Path:
    for parent in ("libs", "services"):
        candidate = REPO / parent / module / module
        if candidate.is_dir():
            return candidate
    raise AssertionError(f"no package directory for module '{module}'")


def import_graph(include_tests: bool = False) -> dict[str, set[str]]:
    """Which modules each module imports, from the import statements themselves."""
    graph: dict[str, set[str]] = defaultdict(set)
    for module in MODULES:
        root = _package_root(module)
        sources = root.rglob("*.py") if include_tests else root.glob("*.py")
        for source in sources:
            for line in source.read_text(encoding="utf-8", errors="replace").splitlines():
                match = _IMPORT.match(line)
                if not match:
                    continue
                imported = (match.group(1) or match.group(2)).split(".")[0]
                if imported in MODULES and imported != module:
                    graph[module].add(imported)
    return dict(graph)


def find_cycles(graph: dict[str, set[str]]) -> list[tuple[str, ...]]:
    """Every distinct cycle, reported as the path that closes it."""
    cycles: list[tuple[str, ...]] = []
    seen: set[frozenset[str]] = set()

    def walk(node: str, path: tuple[str, ...], visiting: set[str]) -> None:
        for nxt in sorted(graph.get(node, ())):
            if nxt in visiting:
                cycle = path[path.index(nxt) :] + (nxt,)
                key = frozenset(cycle)
                if key not in seen:
                    seen.add(key)
                    cycles.append(cycle)
                continue
            walk(nxt, (*path, nxt), visiting | {nxt})

    for module in sorted(graph):
        walk(module, (module,), {module})
    return cycles


# ------------------------------------------------------------ The two rules


def test_there_are_no_circular_dependencies_between_modules() -> None:
    """01.18's architectural rule, and the one no single module can check.

    A cycle needs at least two modules to exist and every module in it looks
    correct on its own, so this is precisely the property that has to be
    asserted about the graph rather than about a module.
    """
    cycles = find_cycles(import_graph())
    assert not cycles, (
        "circular dependencies between modules: "
        + "; ".join(" -> ".join(cycle) for cycle in cycles)
        + ". 01 requires the architecture be refactored immediately when one is detected."
    )


#: Layer 0 is a library of individually named mechanisms, not a peer module
#: with a Gateway interface. 21A §5.2 names the nine kernel mechanisms
#: separately and every Gateway imports them by name — `from kernel.journal
#: import ImmutableJournal` is using the library as designed, not reaching past
#: anything. The rule 01.18 states is about Gateways not calling into each
#: other's internals, and that is what this checks.
SUBSTRATE = frozenset({"kernel", "core", "persistence"})


def test_no_gateway_reaches_into_another_gateways_internals() -> None:
    """01.18 — modules interact through published interfaces, not internals.

    A cross-Gateway import must name the other module's package, not a
    submodule of it. `from memory_gateway import MemoryGateway` takes the
    published surface; `from memory_gateway.entries import ...` takes a path
    around the `__init__` that defines what the module offers, and the two
    diverge the moment that `__init__` is curated.

    Layer 0 is exempt, for the reason recorded on `SUBSTRATE` above.
    """
    offenders: list[str] = []
    for module in sorted(MODULES):
        root = _package_root(module)
        for source in root.glob("*.py"):
            for number, line in enumerate(source.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
                match = re.match(r"^\s*from\s+([A-Za-z_][\w.]*)\s+import", line)
                if not match:
                    continue
                target = match.group(1)
                head = target.split(".")[0]
                if head in MODULES and head not in SUBSTRATE and head != module and "." in target:
                    offenders.append(f"{module}/{source.name}:{number} imports {target}")
    # Known and deliberate: two adapters narrow a Done module's surface rather
    # than widening it, which Part IV §17 prefers to editing a finished module.
    # Listed so the exception is visible rather than implied.
    permitted = ("security_gateway.enums", "integration_registry.manifests")
    unexplained = [o for o in offenders if not any(p in o for p in permitted)]
    assert not unexplained, "these imports reach past a Gateway's published interface: " + "; ".join(unexplained)


# ---------------------------------------------------------------- The shape


def test_layer_zero_depends_on_nothing_above_it() -> None:
    """21A §7 — the substrate is beneath everything and reaches up to nothing.

    `kernel` and `core` are imported by every Gateway. If either ever imported
    a Gateway back, the substrate would depend on what it substrates, and the
    build order the whole plan rests on would stop being a build order.
    """
    graph = import_graph()
    for foundation in ("kernel", "core"):
        if foundation not in MODULES:
            continue
        upward = {m for m in graph.get(foundation, set()) if m not in ("kernel", "core", "persistence")}
        assert not upward, f"'{foundation}' imports {sorted(upward)}, which sit above it"


def test_the_graph_is_read_from_imports_not_from_a_list() -> None:
    """Guards the guard.

    A dependency graph maintained by hand is a second description of the
    architecture, and when it disagrees with the imports it is the imports
    that are true. This asserts the graph is non-trivial and covers the
    modules that exist, so a broken parser cannot pass by finding nothing.
    """
    graph = import_graph()
    assert len(MODULES) >= 20, f"expected the full module set, found {len(MODULES)}"
    assert graph, "the import graph is empty; the parser is not reading imports"
    # Every Gateway depends on the kernel; if none appears to, the parse failed.
    depends_on_kernel = [m for m, deps in graph.items() if "kernel" in deps]
    assert len(depends_on_kernel) >= 10, (
        f"only {len(depends_on_kernel)} modules appear to import the kernel; the parse is wrong"
    )


@pytest.mark.parametrize("module", sorted(MODULES))
def test_every_module_is_importable_by_name(module: str) -> None:
    """A module nothing can import is a module nothing can depend on."""
    root = _package_root(module)
    assert (root / "__init__.py").exists(), f"'{module}' has no package __init__"
