# Run flake8 on main source dir and documentation.
import sys
from collections import defaultdict
from pathlib import Path
from subprocess import Popen, PIPE

import pytest

import ase

pytest.importorskip('flake8')

asepath = Path(ase.__path__[0])  # type: ignore

max_errors = {
    # do not compare types, use 'isinstance()'
    'E721': 0,
    # multiple imports on one line
    'E401': 0,
    # multiple spaces before keyword
    'E272': 0,
    # continuation line under-indented for hanging indent
    'E121': 0,
    # whitespace before '('
    'E211': 0,
    # continuation line with same indent as next logical line
    'E125': 0,
    # comparison to True should be 'if cond is True:' or 'if cond:'
    'E712': 0,
    # 'name' imported but unused
    'F401': 0,
    # no newline at end of file
    'W292': 0,
    # missing whitespace after keyword
    'E275': 0,
    # multiple spaces after operator
    'E222': 0,
    # missing whitespace around modulo operator
    'E228': 0,
    # expected 1 blank line before a nested definition, found 0
    'E306': 0,
    # test for membership should be 'not in'
    'E713': 0,
    # multiple statements on one line (colon)
    'E701': 0,
    # indentation is not a multiple of four (comment)
    'E114': 0,
    # unexpected indentation (comment)
    'E116': 0,
    # comparison to None should be 'if cond is None:'
    'E711': 0,
    # expected 1 blank line, found 0
    'E301': 0,
    # multiple spaces after keyword
    'E271': 6,
    # test for object identity should be 'is not'
    'E714': 0,
    # closing bracket does not match visual indentation
    'E124': 0,
    # too many leading '#' for block comment
    'E266': 0,
    # over-indented
    'E117': 0,
    # indentation contains mixed spaces and tabs
    'E101': 0,
    # indentation contains tabs
    'W191': 0,
    # closing bracket does not match indentation of opening bracket's line
    'E123': 13,
    # multiple spaces before operator
    'E221': 4,
    # whitespace before '}'
    'E202': 16,
    # whitespace after '{'
    'E201': 16,
    # inline comment should start with '# '
    'E262': 12,
    # the backslash is redundant between brackets
    'E502': 8,
    # continuation line missing indentation or outdented
    'E122': 0,
    # indentation is not a multiple of four
    'E111': 28,
    # do not use bare 'except'
    'E722': 0,
    # whitespace before ':'
    'E203': 38,
    # blank line at end of file
    'W391': 39,
    # continuation line over-indented for hanging indent
    'E126': 27,
    # multiple spaces after ','
    'E241': 45,
    # continuation line under-indented for visual indent
    'E128': 39,
    # continuation line over-indented for visual indent
    'E127': 32,
    # missing whitespace around operator
    'E225': 43,
    # ambiguous variable name 'O'
    'E741': 77,
    # too many blank lines (2)
    'E303': 188,
    # expected 2 blank lines after class or function definition, found 1
    'E305': 35,
    # module level import not at top of file
    'E402': 0,
    # at least two spaces before inline comment
    'E261': 71,
    # expected 2 blank lines, found 1
    'E302': 102,
    # unexpected spaces around keyword / parameter equals
    'E251': 95,
    # trailing whitespace
    'W291': 169,
    # block comment should start with '# '
    'E265': 172,
    # missing whitespace after ','
    'E231': 369,
    # missing whitespace around arithmetic operator
    'E226': 408,
    # line too long (93 > 79 characters)
    'E501': 755}


def have_documentation():
    import ase
    ase_path = Path(ase.__path__[0])
    doc_path = ase_path.parent / 'doc/ase/ase.rst'
    return doc_path.is_file()


@pytest.mark.slow
def test_flake8():
    if not have_documentation():
        pytest.skip('ase/doc not present; '
                    'this is probably an installed version ')

    args = [
        sys.executable,
        '-m',
        'flake8',
        str(asepath),
        str((asepath / '../doc').resolve()),
        '--exclude',
        str((asepath / '../doc/build/*').resolve()),
        '--ignore',
        'E129,W293,W503,W504,E741',
        '-j',
        '1'
    ]
    proc = Popen(args, stdout=PIPE)
    stdout, stderr = proc.communicate()
    stdout = stdout.decode('utf8')

    errors = defaultdict(int)
    files = defaultdict(int)
    offenses = defaultdict(list)
    descriptions = {}
    for stdout_line in stdout.splitlines():
        tokens = stdout_line.split(':', 3)
        filename, _, colno, complaint = tokens
        e = complaint.strip().split()[0]
        errors[e] += 1
        descriptions[e] = complaint
        files[filename] += 1
        offenses[e] += [stdout_line]

    errmsg = ''
    for err, nerrs in errors.items():
        nmaxerrs = max_errors.get(err, 0)
        if nerrs <= nmaxerrs:
            continue
        errmsg += 'Too many flakes: {} (max={})\n'.format(nerrs, nmaxerrs)
        errmsg += 'Offenses:\n' + '\n'.join(offenses[err]) + '\n'

    assert errmsg == '', errmsg
