import os
import re
import ipaddress
import sys
import json

IPV4SEG  = r'(?:25[0-5]|(?:2[0-4]|1{0,1}[0-9]){0,1}[0-9])'
IPV4ADDR = r'\b(?:(?:' + IPV4SEG + r'\.){3,3}' + IPV4SEG + r')\b'
IPV6SEG  = r'(?:(?:[0-9a-fA-F]){1,4})'
IPV6GROUPS = (
    r'(?:' + IPV6SEG + r':){7,7}' + IPV6SEG,                  # 1:2:3:4:5:6:7:8
    r'\b(?:' + IPV6SEG + r':){1,7}:',                           # 1::                                 1:2:3:4:5:6:7::
    r'(?:' + IPV6SEG + r':){1,6}:' + IPV6SEG,                 # 1::8               1:2:3:4:5:6::8   1:2:3:4:5:6::8
    r'(?:' + IPV6SEG + r':){1,5}(?::' + IPV6SEG + r'){1,2}',  # 1::7:8             1:2:3:4:5::7:8   1:2:3:4:5::8
    r'(?:' + IPV6SEG + r':){1,4}(?::' + IPV6SEG + r'){1,3}',  # 1::6:7:8           1:2:3:4::6:7:8   1:2:3:4::8
    r'(?:' + IPV6SEG + r':){1,3}(?::' + IPV6SEG + r'){1,4}',  # 1::5:6:7:8         1:2:3::5:6:7:8   1:2:3::8
    r'(?:' + IPV6SEG + r':){1,2}(?::' + IPV6SEG + r'){1,5}',  # 1::4:5:6:7:8       1:2::4:5:6:7:8   1:2::8
    IPV6SEG + r':(?:(?::' + IPV6SEG + r'){1,6})',             # 1::3:4:5:6:7:8     1::3:4:5:6:7:8   1::8
    r':(?:(?::' + IPV6SEG + r'){1,7}|:)',                     # ::2:3:4:5:6:7:8    ::2:3:4:5:6:7:8  ::8       ::
    r'fe80:(?::' + IPV6SEG + r'){0,4}%[0-9a-zA-Z]{1,}',       # fe80::7:8%eth0     fe80::7:8%1  (link-local IPv6 addresses with zone index)
    r'::(?:ffff(?::0{1,4}){0,1}:){0,1}[^\s:]' + IPV4ADDR,     # ::255.255.255.255  ::ffff:255.255.255.255  ::ffff:0:255.255.255.255 (IPv4-mapped IPv6 addresses and IPv4-translated addresses)
    r'(?:' + IPV6SEG + r':){1,4}:[^\s:]' + IPV4ADDR,          # 2001:db8:3:4::192.0.2.33  64:ff9b::192.0.2.33 (IPv4-Embedded IPv6 Address)
)
IPV6ADDR = '|'.join(['(?:{})'.format(g) for g in IPV6GROUPS[::-1]])  # Reverse rows for greedy match

SUPPORTED_EXTS = ('.md', '.rst', '.txt')

# Linter only applies to published documentation sources under docs/. Repo-root
# files (README.md, AGENTS.md, .github/copilot-instructions.md) are project
# meta, not docs content, and are out of scope.
DOCS_ROOT = 'docs'

# Subtrees under docs/ that are excluded from the build (per docs/conf.py)
# and therefore also excluded from lint.
DOCS_EXCLUDED_SUBDIRS = ('_build', '_rst_legacy')


def is_docs_path(path):
    """Return True iff `path` resolves under the repo's `docs/` tree AND
    is not inside one of the build-excluded subtrees (``_build``,
    ``_rst_legacy``).

    Accepts both repo-relative and absolute paths. Both `path` and
    `DOCS_ROOT` are resolved with `os.path.realpath`, so symlinks are
    followed to their real targets — a symlink under `docs/` that
    points outside the tree is correctly treated as out-of-scope, and
    a `docs/` that is itself a symlink (e.g., in some CI checkouts) is
    correctly treated as the docs root. Paths are normalized against
    the linter's working directory (CI invokes it from the repo root;
    the same is expected for local runs).
    """
    abs_path = os.path.realpath(path)
    abs_docs = os.path.realpath(DOCS_ROOT)
    try:
        if os.path.commonpath([abs_path, abs_docs]) != abs_docs:
            return False
    except ValueError:
        # commonpath raises on mixed drives (Windows) or empty input.
        return False
    for excluded in DOCS_EXCLUDED_SUBDIRS:
        abs_excluded = os.path.realpath(os.path.join(DOCS_ROOT, excluded))
        try:
            if os.path.commonpath([abs_path, abs_excluded]) == abs_excluded:
                return False
        except ValueError:
            continue
    return True

# MyST / Markdown fenced code block: leading whitespace + 3+ backticks or 3+ colons.
# Same character and length-or-greater closes.
MD_FENCE_RE = re.compile(r'^(\s*)(`{3,}|:{3,})(.*)$')

# RST `.. code-block::` directive: leading whitespace + literal `.. code-block::`.
# Anchored to start-of-line so prose mentions like `\`\`.. code-block::\`\`` inside
# a Markdown paragraph (see docs/documentation.md) don't false-trigger the
# code-block tracker.
RST_CODEBLOCK_RE = re.compile(r'^(\s*)\.\.\s+code-block::')

# MyST directive names whose body is code-like — line-length exception applies.
# Anything else with a `{directive}` info string is treated as prose-bearing
# (`{note}`, `{warning}`, `{tip}`, `{deprecated}`, …); their content is normal
# Markdown and gets line-length checked. Plain fences with no info string OR a
# bare language tag (`python`, `bash`, `yaml`, …) are code blocks per
# CommonMark and always skip line-length.
CODE_BEARING_DIRECTIVES = frozenset({
    'code-block', 'code', 'sourcecode',
    'cfgcmd', 'opcmd', 'cmdinclude', 'cmdincludemd',
    'literalinclude', 'parsed-literal', 'raw',
    'command-output',
    'eval-rst',  # body is RST; its own line-length is handled via the
                 # `.. code-block::` tracker for nested code blocks.
})


def _fence_is_code(info):
    """Return True iff the fence opener `info` string designates a code-like block.

    Used to gate the line-length-check skip — only code-like fences should
    suppress line-length linting; prose-bearing directive fences like
    `{note}` / `{warning}` must still have their content checked.
    """
    info = info.strip()
    if not info:
        return True  # plain ``` is code per CommonMark
    if not info.startswith('{'):
        return True  # python, bash, yaml, text, etc.
    # `{code-block} python` -> `code-block`; `{note}` -> `note`.
    name = info[1:].split('}', 1)[0].strip()
    return name in CODE_BEARING_DIRECTIVES


SUPPRESSION_MARKER_RE = {
    'rst': {
        'stop': re.compile(r'^\s*\.\.\s+stop_vyoslinter\s*$'),
        'start': re.compile(r'^\s*\.\.\s+start_vyoslinter\s*$'),
    },
    'md': {
        'stop': re.compile(r'^\s*%\s+stop_vyoslinter\s*$'),
        'start': re.compile(r'^\s*%\s+start_vyoslinter\s*$'),
    },
}


def is_suppression_marker(line, kind, in_md_fence, in_rst_codeblock,
                          md_fence_is_eval_rst, file_ext):
    """Detect valid stop/start markers in the parser context where they apply.

    `% ...` is only valid in MyST Markdown (`.md`) at top level (outside any fence).
    `.. ...` is valid in `.rst`/`.txt` at top level (outside RST code-block) and
    in `.md` only when inside an `{eval-rst}` fence.
    """
    if SUPPRESSION_MARKER_RE['md'][kind].match(line):
        return file_ext == '.md' and not in_md_fence
    if not SUPPRESSION_MARKER_RE['rst'][kind].match(line):
        return False
    if in_rst_codeblock:
        return False
    if file_ext in ('.rst', '.txt'):
        return True
    if in_md_fence:
        return md_fence_is_eval_rst
    return False


def lint_ipv4(cnt, line):
    """Flag IPv4 addresses outside RFC 5737 / private / multicast ranges.

    Iterates over every IPv4 match on the line — a line with an
    allowed address followed by a real public address must not
    pass just because the first match is allowed.
    """
    for match in re.finditer(IPV4ADDR, line, re.I):
        ip = ipaddress.ip_address(match.group().strip(' '))
        # https://docs.python.org/3/library/ipaddress.html#ipaddress.IPv4Address.is_private
        if ip.is_private:
            continue
        if ip.is_multicast:
            continue
        if ip.is_global is False:
            continue
        return (f"Use IPv4 reserved for Documentation (RFC 5737) or private space: {ip}", cnt, 'error')
    return None


def lint_ipv6(cnt, line):
    """Flag IPv6 addresses outside RFC 3849 / private / multicast ranges.

    Iterates over every IPv6 match on the line — same all-matches
    discipline as `lint_ipv4`.
    """
    for match in re.finditer(IPV6ADDR, line, re.I):
        ip = ipaddress.ip_address(match.group().strip(' '))
        if ip.is_private:
            continue
        if ip.is_multicast:
            continue
        if ip.is_global is False:
            continue
        return (f"Use IPv6 reserved for Documentation (RFC 3849) or private space: {ip}", cnt, 'error')
    return None


def lint_linelen(cnt, line):
    """Warn when a line exceeds the 80-character docs convention."""
    line = line.rstrip()
    if len(line) > 80:
        return (f"Line too long: len={len(line)}", cnt, 'warning')

def handle_file_action(filepath):
    """Run all lint checks on one file, respecting fence/code-block and suppression context."""
    errors = []
    file_ext = os.path.splitext(filepath)[1].lower()
    # Stack of open MD/MyST fences: (char, min_len, is_code). Supports
    # nesting like `:::{note}` containing `::::{code-block}`, where the
    # inner opener does not close the outer note (CommonMark closing rule:
    # matching closer must have no info string after the fence chars).
    # `is_code` records whether THAT fence is a code-bearing one — gates the
    # line-length skip per the innermost (top-of-stack) entry.
    md_fence_stack = []
    md_fence_is_eval_rst = False
    in_rst_codeblock = False
    rst_codeblock_indent = 0
    start_vyoslinter = True
    cnt = 0

    with open(filepath) as fp:
        for cnt, line in enumerate(fp, start=1):
            # MD/MyST fenced code block tracking (``` or :::).
            fence_match = MD_FENCE_RE.match(line)
            if fence_match:
                fence = fence_match.group(2)
                fence_char = fence[0]
                fence_len = len(fence)
                info = fence_match.group(3).strip()
                # A closer matches the top of the stack (same char, len >=
                # opener) and has no info string. Anything else opens a new
                # (possibly nested) fence.
                is_closer = (
                    md_fence_stack
                    and not info
                    and fence_char == md_fence_stack[-1][0]
                    and fence_len >= md_fence_stack[-1][1]
                )
                if is_closer:
                    md_fence_stack.pop()
                    if not md_fence_stack:
                        md_fence_is_eval_rst = False
                else:
                    if not md_fence_stack:
                        md_fence_is_eval_rst = info.startswith('{eval-rst}')
                    md_fence_stack.append((fence_char, fence_len, _fence_is_code(info)))

            in_md_fence = bool(md_fence_stack)
            in_md_code_fence = bool(md_fence_stack) and md_fence_stack[-1][2]

            # RST `.. code-block::` tracking (existing semantics for .rst/.txt).
            # Each `.. code-block::` directive resets the tracked indent so a
            # later dedent past that column exits the block — even when the
            # directive itself appears inside an already-open outer block.
            #
            # Exit when the next non-blank line's leading-whitespace count is
            # <= the directive's column. The body of an RST code-block must
            # be indented MORE than the directive itself, so leading-ws at or
            # below `rst_codeblock_indent` signals the block has ended.
            #
            # Previously this used `len(line) > rst_codeblock_indent and not
            # line[rst_codeblock_indent].isspace()`, which silently skipped
            # the exit check on lines shorter than `rst_codeblock_indent + 1`
            # chars — e.g., a 3-char dedented line under a directive at
            # column 4 left the block open, suppressing line-length checks
            # downstream.
            if in_rst_codeblock and line.strip():
                leading = len(line) - len(line.lstrip())
                if leading <= rst_codeblock_indent:
                    in_rst_codeblock = False
            # Only treat `.. code-block::` as a directive opener in RST/TXT
            # files or inside an `{eval-rst}` MyST fence. In plain Markdown
            # the same characters can appear as prose (e.g., backtick-quoted
            # mentions of the directive name) and must not open a block.
            if file_ext in ('.rst', '.txt') or md_fence_is_eval_rst:
                rst_open = RST_CODEBLOCK_RE.match(line)
                if rst_open:
                    in_rst_codeblock = True
                    rst_codeblock_indent = len(rst_open.group(1))

            if is_suppression_marker(
                line, 'stop', in_md_fence, in_rst_codeblock,
                md_fence_is_eval_rst, file_ext,
            ):
                start_vyoslinter = False
            if is_suppression_marker(
                line, 'start', in_md_fence, in_rst_codeblock,
                md_fence_is_eval_rst, file_ext,
            ):
                start_vyoslinter = True

            if not start_vyoslinter:
                continue

            # Only code-bearing fences (plain ```python```, `{code-block}`,
            # `{cfgcmd}`, etc.) skip line-length. Prose-bearing directives
            # like `{note}` and `{warning}` have their content checked.
            test_line_length = not (in_md_code_fence or in_rst_codeblock)

            err_ip4 = lint_ipv4(cnt, line.strip())
            err_ip6 = lint_ipv6(cnt, line.strip())
            err_len = lint_linelen(cnt, line) if test_line_length else None
            for e in (err_ip4, err_ip6, err_len):
                if e:
                    errors.append(e)

        if not start_vyoslinter:
            errors.append(("Don't forget to turn linter back on", cnt, 'error'))

    if len(errors) > 0:
        '''
        "::{$type} file={$filename},line={$line},col=$column::{$log}"
        '''
        print(f"File: {filepath}")
        for error in errors:
            print(f"::{error[2]} file={filepath},line={error[1]}::{error[0]}")
        print('')
        return False


def main():
    """Entry point: lint the changed-file list from argv, or fall back to walking `docs/`."""
    bool_error = True
    # Only the argv-parsing step is wrapped in try/except. Errors raised by
    # handle_file_action() must propagate so CI failures stay visible instead
    # of silently triggering a full docs/ walk.
    #
    # Accepts one or more positional argv entries, each a JSON array of
    # paths (e.g., `'["foo.md", "bar.rst"]'`). Arrays are merged and
    # deduplicated before linting. CI passes `files_modified`,
    # `files_added`, etc. as separate args — see lint-doc.yml.
    if len(sys.argv) <= 1:
        files = None
    else:
        try:
            files = []
            for arg in sys.argv[1:]:
                if arg.strip():
                    files.extend(json.loads(arg))
            files = sorted(set(files))
        except (json.JSONDecodeError, TypeError):
            # Malformed input -> fall back to walking DOCS_ROOT.
            files = None

    if files is not None:
        for file in files:
            if (
                file.endswith(SUPPORTED_EXTS)
                and is_docs_path(file)
            ):
                if handle_file_action(file) is False:
                    bool_error = False
    else:
        # In-place dirs prune: skip descending into build-excluded subtrees.
        # is_docs_path() also rejects paths under those subtrees, so the
        # prune is an optimization (avoids walking thousands of archived
        # legacy RST files) and the filter is correctness.
        for root, dirs, files in os.walk(DOCS_ROOT):
            dirs[:] = [d for d in dirs if d not in DOCS_EXCLUDED_SUBDIRS]
            for file in files:
                filepath = os.path.join(root, file)
                if (
                    file.endswith(SUPPORTED_EXTS)
                    and is_docs_path(filepath)
                ):
                    if handle_file_action(filepath) is False:
                        bool_error = False

    return bool_error


if __name__ == "__main__":
    if main() == False:
        exit(1)
