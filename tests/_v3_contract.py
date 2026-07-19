"""F6 source-substring contract harness (library).

Parses the two Gate-T dashboard test files with Python's ``ast`` module (never
regex, so unicode escapes / mixed quote styles / ``#`` inside string literals /
normalizers are all handled natively) and proves that every source-substring
assertion is captured with no silent drop.

The harness does NOT re-implement the tests' pass/fail. At baseline it must
agree with them: every literal a Gate-T test asserts is ``in`` its source
fileset lands in the PRESENT set, every literal asserted ``not in`` lands in the
ABSENT set, and re-checking those against the *current* source reproduces the
exact same pass/fail as the original tests.

This module only ever READS the two Gate-T test files and the dashboard source
tree. It imports nothing from the app and mutates nothing.

Vocabulary
----------
* PRESENT / ABSENT -- ``literal in fileset`` / ``literal not in fileset``.
* fileset / binding -- an ordered set of source files (a single ``read_text`` or
  a helper-built ``files=[...]`` list, globs expanded against the real dirs)
  plus a join separator and an optional normalizer chain (``.lower()`` /
  ``.replace(a, b)``). Binding and polarity are orthogonal (4 valid combos).
* E1 -- structural / value assert (``==``, ``!=``, ``set(...)``, ``len(...)``,
  ``is True``, bare bool): not a single ``in``/``not in`` compare.
* E2 -- non-source-bound / build-conditional assert (e.g. ``bundle_text`` joined
  from the compiled ``webui/static/v2/dist`` bundle, guarded by an early return
  when dist is absent).
* E3 -- an assert matching none of the recognised shapes: a hard error naming
  ``file:lineno`` so a new/unexpected form can never be silently skipped.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent            # tests/
REPO_ROOT = HERE.parent                            # repo root
SOURCE_TREE = REPO_ROOT / "webui" / "v2_src"       # everything under here is "source"

GATE_T_FILES = [
    HERE / "test_daily_ohlcv_dashboard_tab.py",
    HERE / "test_stom_rl_dashboard_tab.py",
]
SNAPSHOT_PATH = HERE / "_v3_contract_snapshot.json"

SCHEMA_VERSION = 1


class ContractError(AssertionError):
    """Raised on an unclassifiable assert (E3) or a broken invariant."""


# --------------------------------------------------------------------------- #
# Small ast helpers
# --------------------------------------------------------------------------- #
def _is_str_const(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, str)


def _all_str_const(nodes) -> bool:
    return bool(nodes) and all(_is_str_const(n) for n in nodes)


def _literal_str(node: ast.AST):
    """Decode a string-constant node to its real Python ``str`` (or ``None``).

    Uses ``ast.literal_eval`` so ``"Kronos \\ub300\\uc2dc\\ubcf4\\ub4dc"``
    becomes real Hangul, the mixed-quote ``'"name": "kronos-dashboard"'``
    survives intact, and a ``#`` inside a literal is never mistaken for a
    comment.
    """
    if not _is_str_const(node):
        return None
    return ast.literal_eval(node)


def _short_form(node: ast.AST) -> str:
    try:
        return ast.unparse(node)
    except Exception:  # pragma: no cover - defensive
        return ast.dump(node)


def _child_stmt_bodies(stmt: ast.AST):
    """Yield the nested statement lists of a compound statement.

    ``ast.For`` is handled by the callers (it carries loop semantics), so it is
    intentionally not expanded here.
    """
    if isinstance(stmt, ast.FunctionDef):
        yield stmt.body
    elif isinstance(stmt, ast.If):
        yield stmt.body
        yield stmt.orelse
    elif isinstance(stmt, ast.With):
        yield stmt.body
    elif isinstance(stmt, ast.While):
        yield stmt.body
        yield stmt.orelse
    elif isinstance(stmt, ast.Try):
        yield stmt.body
        for handler in stmt.handlers:
            yield handler.body
        yield stmt.orelse
        yield stmt.finalbody


# --------------------------------------------------------------------------- #
# Path constant resolution (SRC / DASHBOARD_SRC / dist / Path(__file__)...)
# --------------------------------------------------------------------------- #
def _resolve_path(node: ast.AST, path_env: dict, current_file: Path):
    """Resolve a path expression to a real ``Path`` or ``None``.

    Handles ``Path(__file__).resolve().parents[n]`` (using the real file being
    parsed), ``NAME`` lookups, and ``base / 'segment'`` ``/`` chains.
    """
    if isinstance(node, ast.Name):
        return path_env.get(node.id)

    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        left = _resolve_path(node.left, path_env, current_file)
        seg = _literal_str(node.right)
        if left is None or seg is None:
            return None
        return left / seg

    if isinstance(node, ast.Call):
        func = node.func
        # Path(__file__)
        if (
            isinstance(func, ast.Name)
            and func.id == "Path"
            and len(node.args) == 1
            and isinstance(node.args[0], ast.Name)
            and node.args[0].id == "__file__"
        ):
            return current_file
        # <expr>.resolve()
        if isinstance(func, ast.Attribute) and func.attr == "resolve":
            base = _resolve_path(func.value, path_env, current_file)
            return base.resolve() if base is not None else None
        return None

    if isinstance(node, ast.Subscript):
        # <expr>.parents[n]
        value = node.value
        if isinstance(value, ast.Attribute) and value.attr == "parents":
            base = _resolve_path(value.value, path_env, current_file)
            idx = _const_int(node.slice)
            if base is not None and idx is not None:
                return base.parents[idx]
        return None

    return None


def _const_int(node: ast.AST):
    if isinstance(node, ast.Constant) and isinstance(node.value, int):
        return node.value
    # Python <3.9 wrapped subscripts in ast.Index; py3.11 does not, but be safe.
    if isinstance(node, ast.Index):  # pragma: no cover - legacy ast
        return _const_int(node.value)
    return None


def _rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT).as_posix()


def _is_source_rel(rel: str) -> bool:
    return rel == "webui/v2_src" or rel.startswith("webui/v2_src/")


# --------------------------------------------------------------------------- #
# Source binding (fileset) construction
# --------------------------------------------------------------------------- #
def _file_component(path: Path):
    return {"kind": "file", "path": _rel(path)}


def _glob_component(dir_path: Path, pattern: str, is_sorted: bool):
    return {"kind": "glob", "dir": _rel(dir_path), "pattern": pattern, "sorted": bool(is_sorted)}


def _component_source_rel(component: dict) -> str:
    return component["path"] if component["kind"] == "file" else component["dir"]


def _new_binding(components, separator="\n", normalizers=None):
    normalizers = list(normalizers or [])
    non_source = not all(_is_source_rel(_component_source_rel(c)) for c in components)
    return {
        "components": list(components),
        "separator": separator,
        "normalizers": normalizers,
        "non_source": non_source,
    }


def _with_normalizer(binding: dict, attr: str, args) -> dict:
    normalizers = list(binding["normalizers"])
    if attr == "lower":
        normalizers.append({"kind": "lower"})
    elif attr == "replace":
        if len(args) != 2:
            return None
        old = _literal_str(args[0])
        new = _literal_str(args[1])
        if old is None or new is None:
            return None
        normalizers.append({"kind": "replace", "old": old, "new": new})
    else:  # unsupported normalizer -> treat comparator as unresolved
        return None
    clone = dict(binding)
    clone["normalizers"] = normalizers
    return clone


def _spec_key(binding: dict) -> str:
    parts = []
    for c in binding["components"]:
        if c["kind"] == "file":
            parts.append(c["path"])
        else:
            prefix = "glob:sorted:" if c.get("sorted") else "glob:"
            parts.append(f"{prefix}{c['dir']}/{c['pattern']}")
    key = " + ".join(parts)
    for n in binding["normalizers"]:
        if n["kind"] == "lower":
            key += " ::lower"
        elif n["kind"] == "replace":
            key += f" ::replace({n['old']!r}->{n['new']!r})"
    return key


def _resolve_iter_components(node: ast.AST, path_env: dict, current_file: Path):
    """Resolve the iterable of a ``files=[...]`` / join genexp into components."""
    if isinstance(node, ast.List):
        components = []
        for elt in node.elts:
            p = _resolve_path(elt, path_env, current_file)
            if p is None:
                return None
            components.append(_file_component(p))
        return components
    if isinstance(node, ast.Call):
        func = node.func
        # sorted(<glob>)
        if isinstance(func, ast.Name) and func.id == "sorted" and len(node.args) == 1:
            inner = _resolve_iter_components(node.args[0], path_env, current_file)
            if inner is None:
                return None
            for c in inner:
                if c["kind"] == "glob":
                    c["sorted"] = True
            return inner
        # <dir>.glob(pattern)
        if isinstance(func, ast.Attribute) and func.attr == "glob" and len(node.args) == 1:
            dir_path = _resolve_path(func.value, path_env, current_file)
            pattern = _literal_str(node.args[0])
            if dir_path is None or pattern is None:
                return None
            return [_glob_component(dir_path, pattern, is_sorted=False)]
    return None


def _materialize(binding: dict) -> str:
    """Reconstruct the exact concatenated (and normalized) text for a binding."""
    texts = []
    for c in binding["components"]:
        if c["kind"] == "file":
            texts.append((REPO_ROOT / c["path"]).read_text(encoding="utf-8"))
        else:
            directory = REPO_ROOT / c["dir"]
            paths = list(directory.glob(c["pattern"]))
            if c.get("sorted"):
                paths = sorted(paths)
            for p in paths:
                texts.append(p.read_text(encoding="utf-8"))
    text = binding["separator"].join(texts)
    for n in binding["normalizers"]:
        if n["kind"] == "lower":
            text = text.lower()
        elif n["kind"] == "replace":
            text = text.replace(n["old"], n["new"])
    return text


# --------------------------------------------------------------------------- #
# Snapshot builder
# --------------------------------------------------------------------------- #
class _SnapshotBuilder:
    def __init__(self):
        self.present = {}   # key -> set[str]
        self.absent = {}    # key -> set[str]
        self.bindings = {}  # key -> binding spec
        self.e1 = []
        self.e2 = []

        self.present_count = 0
        self.absent_count = 0
        self.loop_present_expanded = 0
        self.loop_absent_expanded = 0
        self.loop_nodes = 0
        self.e1_count = 0
        self.e2_count = 0

        self.physical_assert_nodes = 0
        self.total_asserts_expanded = 0
        self.per_file = {}

    # -- source-expression resolution ------------------------------------- #
    def _resolve_source(self, node, path_env, src_env, helpers, current_file, helper_cache):
        """Resolve an expression to a source binding, or ``None`` if it is not
        source-bound."""
        if isinstance(node, ast.Name):
            return src_env.get(node.id)

        if isinstance(node, ast.Call):
            func = node.func
            # helper call: NAME() with no args
            if (
                isinstance(func, ast.Name)
                and func.id in helpers
                and not node.args
                and not node.keywords
            ):
                return self._resolve_helper(func.id, path_env, helpers, current_file, helper_cache)

            if isinstance(func, ast.Attribute):
                attr = func.attr
                if attr == "read_text":
                    p = _resolve_path(func.value, path_env, current_file)
                    if p is None:
                        return None
                    return _new_binding([_file_component(p)])
                if attr == "join":
                    sep = _literal_str(func.value)
                    if sep is None or len(node.args) != 1:
                        return None
                    return self._resolve_join(sep, node.args[0], path_env, current_file)
                if attr in ("replace", "lower"):
                    base = self._resolve_source(
                        func.value, path_env, src_env, helpers, current_file, helper_cache
                    )
                    if base is None:
                        return None
                    return _with_normalizer(base, attr, node.args)
        return None

    def _resolve_join(self, sep, arg, path_env, current_file):
        if not isinstance(arg, ast.GeneratorExp):
            return None
        # elt must be `<name>.read_text(...)`
        elt = arg.elt
        if not (
            isinstance(elt, ast.Call)
            and isinstance(elt.func, ast.Attribute)
            and elt.func.attr == "read_text"
        ):
            return None
        if len(arg.generators) != 1:
            return None
        comp = arg.generators[0]
        components = _resolve_iter_components(comp.iter, path_env, current_file)
        if components is None:
            return None
        return _new_binding(components, separator=sep)

    def _resolve_helper(self, name, path_env, helpers, current_file, helper_cache):
        if name in helper_cache:
            return helper_cache[name]
        func = helpers[name]
        components = []
        separator = "\n"
        for stmt in func.body:
            if isinstance(stmt, ast.Assign):
                # files = [ ... ]
                if (
                    len(stmt.targets) == 1
                    and isinstance(stmt.targets[0], ast.Name)
                    and stmt.targets[0].id == "files"
                    and isinstance(stmt.value, ast.List)
                ):
                    resolved = _resolve_iter_components(stmt.value, path_env, current_file)
                    if resolved is None:
                        raise ContractError(
                            f"helper {name!r}: could not resolve files=[...] list"
                        )
                    components = resolved
                continue
            if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
                call = stmt.value
                # files.extend(...) / files.append(...)
                if (
                    isinstance(call.func, ast.Attribute)
                    and isinstance(call.func.value, ast.Name)
                    and call.func.value.id == "files"
                    and call.func.attr in ("extend", "append")
                    and len(call.args) == 1
                ):
                    if call.func.attr == "extend":
                        extra = _resolve_iter_components(call.args[0], path_env, current_file)
                        if extra is None:
                            raise ContractError(
                                f"helper {name!r}: could not resolve files.extend(...)"
                            )
                        components.extend(extra)
                    else:  # append single path
                        p = _resolve_path(call.args[0], path_env, current_file)
                        if p is None:
                            raise ContractError(
                                f"helper {name!r}: could not resolve files.append(...)"
                            )
                        components.append(_file_component(p))
                continue
            if isinstance(stmt, ast.Return):
                ret = stmt.value
                if (
                    isinstance(ret, ast.Call)
                    and isinstance(ret.func, ast.Attribute)
                    and ret.func.attr == "join"
                ):
                    sep = _literal_str(ret.func.value)
                    if sep is not None:
                        separator = sep
                continue
        if not components:
            raise ContractError(f"helper {name!r}: produced an empty fileset")
        binding = _new_binding(components, separator=separator)
        helper_cache[name] = binding
        return binding

    # -- statement walk ---------------------------------------------------- #
    def _walk_stmts(self, stmts, ctx, loop_ctx):
        for stmt in stmts:
            self._visit_stmt(stmt, ctx, loop_ctx)

    def _visit_stmt(self, stmt, ctx, loop_ctx):
        if isinstance(stmt, ast.Assign):
            self._handle_assign(stmt, ctx)
            return
        if isinstance(stmt, ast.Assert):
            self._classify_assert(stmt, ctx, loop_ctx)
            return
        if isinstance(stmt, ast.For):
            new_ctx = loop_ctx
            if (
                isinstance(stmt.target, ast.Name)
                and isinstance(stmt.iter, ast.List)
                and _all_str_const(stmt.iter.elts)
            ):
                lits = [ast.literal_eval(e) for e in stmt.iter.elts]
                new_ctx = (stmt.target.id, lits)
            self._walk_stmts(stmt.body, ctx, new_ctx)
            self._walk_stmts(stmt.orelse, ctx, loop_ctx)
            return
        # generic compound statements
        for body in _child_stmt_bodies(stmt):
            # nested function defs get a fresh source-var scope
            child_ctx = ctx
            if isinstance(stmt, ast.FunctionDef):
                child_ctx = dict(ctx)
                child_ctx["src_env"] = {}
                child_ctx["path_env"] = dict(ctx["module_path_env"])
            self._walk_stmts(body, child_ctx, None if isinstance(stmt, ast.FunctionDef) else loop_ctx)

    def _handle_assign(self, stmt, ctx):
        if len(stmt.targets) != 1 or not isinstance(stmt.targets[0], ast.Name):
            return
        name = stmt.targets[0].id
        binding = self._resolve_source(
            stmt.value,
            ctx["path_env"],
            ctx["src_env"],
            ctx["helpers"],
            ctx["current_file"],
            ctx["helper_cache"],
        )
        if binding is not None:
            ctx["src_env"][name] = binding
            return
        p = _resolve_path(stmt.value, ctx["path_env"], ctx["current_file"])
        if p is not None:
            ctx["path_env"][name] = p
            return
        ctx["src_env"][name] = None  # explicitly unresolved

    # -- assert classification -------------------------------------------- #
    def _classify_assert(self, stmt, ctx, loop_ctx):
        test = stmt.test
        lineno = stmt.lineno
        file_rel = ctx["file_rel"]

        # E1: not a single in/not-in compare
        if not (
            isinstance(test, ast.Compare)
            and len(test.ops) == 1
            and isinstance(test.ops[0], (ast.In, ast.NotIn))
        ):
            self._record_e1(file_rel, lineno, test, loop_ctx)
            return

        polarity = "present" if isinstance(test.ops[0], ast.In) else "absent"
        left = test.left
        comparator = test.comparators[0]

        # literal(s) from the left operand
        if _is_str_const(left):
            lits = [_literal_str(left)]
            is_loop = False
        elif (
            isinstance(left, ast.Name)
            and loop_ctx is not None
            and left.id == loop_ctx[0]
        ):
            lits = list(loop_ctx[1])
            is_loop = True
        else:
            raise ContractError(
                f"E3 unclassifiable assert left at {file_rel}:{lineno}: {_short_form(test)}"
            )

        binding = self._resolve_source(
            comparator,
            ctx["path_env"],
            ctx["src_env"],
            ctx["helpers"],
            ctx["current_file"],
            ctx["helper_cache"],
        )

        # E2: comparator not resolvable to a source fileset (or a build artifact)
        if binding is None or binding.get("non_source"):
            if is_loop:
                raise ContractError(
                    f"E3 loop assert over non-source comparator at {file_rel}:{lineno}: "
                    f"{_short_form(test)}"
                )
            self._record_e2(file_rel, lineno, test, loop_ctx)
            return

        key = _spec_key(binding)
        self.bindings.setdefault(key, binding)
        bucket = (self.present if polarity == "present" else self.absent).setdefault(key, set())
        for lit in lits:
            bucket.add(lit)

        if is_loop:
            self.loop_nodes += 1
            if polarity == "present":
                self.loop_present_expanded += len(lits)
            else:
                self.loop_absent_expanded += len(lits)
        else:
            if polarity == "present":
                self.present_count += 1
            else:
                self.absent_count += 1

    def _record_e1(self, file_rel, lineno, test, loop_ctx):
        if loop_ctx is not None:
            raise ContractError(
                f"E3 structural assert inside a value loop at {file_rel}:{lineno}: "
                f"{_short_form(test)}"
            )
        self.e1.append({"file": file_rel, "lineno": lineno, "form": _short_form(test)})
        self.e1_count += 1

    def _record_e2(self, file_rel, lineno, test, loop_ctx):
        if loop_ctx is not None:
            raise ContractError(
                f"E3 non-source assert inside a value loop at {file_rel}:{lineno}: "
                f"{_short_form(test)}"
            )
        self.e2.append({"file": file_rel, "lineno": lineno, "form": _short_form(test)})
        self.e2_count += 1

    # -- independent counting (silent-drop guard) ------------------------- #
    def _count_logical(self, stmts, loop_len):
        total = 0
        for stmt in stmts:
            if isinstance(stmt, ast.Assert):
                total += loop_len
            elif isinstance(stmt, ast.For):
                inner = loop_len
                if (
                    isinstance(stmt.target, ast.Name)
                    and isinstance(stmt.iter, ast.List)
                    and _all_str_const(stmt.iter.elts)
                ):
                    inner = loop_len * len(stmt.iter.elts)
                total += self._count_logical(stmt.body, inner)
                total += self._count_logical(stmt.orelse, loop_len)
            else:
                for body in _child_stmt_bodies(stmt):
                    total += self._count_logical(body, loop_len)
        return total

    # -- per-file driver --------------------------------------------------- #
    def process_file(self, path: Path):
        current_file = path.resolve()
        tree = ast.parse(current_file.read_text(encoding="utf-8"))
        file_rel = current_file.relative_to(REPO_ROOT).as_posix()

        module_path_env = {}
        helpers = {}
        for node in tree.body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(
                node.targets[0], ast.Name
            ):
                p = _resolve_path(node.value, module_path_env, current_file)
                if p is not None:
                    module_path_env[node.targets[0].id] = p
            elif isinstance(node, ast.FunctionDef):
                helpers[node.name] = node

        helper_cache = {}

        # physical + logical assert counts (independent of classification)
        physical = sum(1 for n in ast.walk(tree) if isinstance(n, ast.Assert))
        logical = self._count_logical(tree.body, 1)
        self.physical_assert_nodes += physical
        self.total_asserts_expanded += logical
        self.per_file[file_rel] = {"physical_assert_nodes": physical, "total_asserts": logical}

        # classify every function's asserts
        for node in tree.body:
            if isinstance(node, ast.FunctionDef):
                ctx = {
                    "path_env": dict(module_path_env),
                    "module_path_env": module_path_env,
                    "src_env": {},
                    "helpers": helpers,
                    "helper_cache": helper_cache,
                    "current_file": current_file,
                    "file_rel": file_rel,
                }
                self._walk_stmts(node.body, ctx, None)

    # -- finalize ---------------------------------------------------------- #
    def to_snapshot(self):
        classified = (
            self.present_count
            + self.absent_count
            + self.loop_present_expanded
            + self.loop_absent_expanded
        )
        counts = {
            "total_asserts": self.total_asserts_expanded,
            "physical_assert_nodes": self.physical_assert_nodes,
            "classified": classified,
            "present": self.present_count,
            "absent": self.absent_count,
            "loop_present_expanded": self.loop_present_expanded,
            "loop_absent_expanded": self.loop_absent_expanded,
            "loop_nodes": self.loop_nodes,
            "e1": self.e1_count,
            "e2": self.e2_count,
            "per_file": self.per_file,
        }
        _check_reconciliation(counts)

        snapshot = {
            "schema_version": SCHEMA_VERSION,
            "counts": counts,
            "bindings": {k: self.bindings[k] for k in sorted(self.bindings)},
            "present": {k: sorted(self.present[k]) for k in sorted(self.present)},
            "absent": {k: sorted(self.absent[k]) for k in sorted(self.absent)},
            "e1": sorted(self.e1, key=lambda r: (r["file"], r["lineno"])),
            "e2": sorted(self.e2, key=lambda r: (r["file"], r["lineno"])),
        }
        return snapshot


def _check_reconciliation(counts: dict) -> None:
    """Hard-fail with a diff if any assert was silently dropped."""
    physical_sum = (
        counts["present"]
        + counts["absent"]
        + counts["loop_nodes"]
        + counts["e1"]
        + counts["e2"]
    )
    if physical_sum != counts["physical_assert_nodes"]:
        raise ContractError(
            "assert-node reconciliation failed (silent drop): "
            f"present({counts['present']}) + absent({counts['absent']}) + "
            f"loop_nodes({counts['loop_nodes']}) + e1({counts['e1']}) + "
            f"e2({counts['e2']}) = {physical_sum} != "
            f"physical_assert_nodes({counts['physical_assert_nodes']})"
        )

    expected_classified = counts["total_asserts"] - counts["e1"] - counts["e2"]
    if counts["classified"] != expected_classified:
        raise ContractError(
            "expanded reconciliation failed (silent drop): "
            f"classified({counts['classified']}) != total_asserts("
            f"{counts['total_asserts']}) - e1({counts['e1']}) - e2({counts['e2']}) "
            f"= {expected_classified}"
        )


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def build_snapshot() -> dict:
    """Parse both Gate-T files and return the contract snapshot dict.

    Raises ``ContractError`` on any unclassifiable assert (E3) or if the
    reconciliation invariant (no silent drops) does not hold.
    """
    if not SOURCE_TREE.is_dir():
        raise ContractError(f"source tree not found: {SOURCE_TREE}")
    for f in GATE_T_FILES:
        if not f.is_file():
            raise ContractError(f"Gate-T test file not found: {f}")

    builder = _SnapshotBuilder()
    for f in GATE_T_FILES:
        builder.process_file(f)
    return builder.to_snapshot()


def verify_snapshot(snapshot: dict) -> None:
    """Re-read the *current* source filesets and assert the contract holds.

    Every PRESENT literal must be ``in`` its concatenated (and normalized)
    fileset, every ABSENT literal must be ``not in`` it, and the recorded counts
    must reconcile. Raises ``ContractError`` on the first violation.
    """
    _check_reconciliation(snapshot["counts"])

    bindings = snapshot["bindings"]

    for key, lits in snapshot["present"].items():
        if key not in bindings:
            raise ContractError(f"present key without a binding: {key!r}")
        text = _materialize(bindings[key])
        for lit in lits:
            if lit not in text:
                raise ContractError(
                    f"PRESENT contract broken: {lit!r} not found in fileset {key!r}"
                )

    for key, lits in snapshot["absent"].items():
        if key not in bindings:
            raise ContractError(f"absent key without a binding: {key!r}")
        text = _materialize(bindings[key])
        for lit in lits:
            if lit in text:
                raise ContractError(
                    f"ABSENT contract broken: {lit!r} unexpectedly found in fileset {key!r}"
                )


def all_present_literals(snapshot: dict) -> set:
    out = set()
    for lits in snapshot["present"].values():
        out.update(lits)
    return out


def all_absent_literals(snapshot: dict) -> set:
    out = set()
    for lits in snapshot["absent"].values():
        out.update(lits)
    return out
