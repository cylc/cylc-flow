# THIS FILE IS PART OF THE CYLC WORKFLOW ENGINE.
# Copyright (C) NIWA & British Crown (Met Office) & Contributors.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from tempfile import NamedTemporaryFile
from contextlib import suppress

import os
import pytest
from pytest import param
import sqlite3
from types import SimpleNamespace

from cylc.flow import __version__ as cylc_version
from cylc.flow.parsec.exceptions import (
    FileParseError,
    IncludeFileNotFoundError,
    Jinja2Error,
    ParsecError,
)
from cylc.flow.parsec.OrderedDict import OrderedDictWithDefaults
from cylc.flow.parsec.fileparse import (
    _prepend_old_templatevars,
    _get_fpath_for_source,
    addict,
    addsect,
    multiline,
    parse,
    read_and_proc,
    merge_template_vars
)


def get_multiline():
    """Data provider for multiline tests. Returned values are:

    file_lines, value, index, maxline, error_message, expected
    """
    r = [
        ([], "'''single line'''", 0, 0, None, ("'''single line'''", 0)),
        (
            ["'''single line"],
            "'''single line",  # missing closing quote
            0,
            0,
            FileParseError,
            {
                'reason': 'Multiline string not closed',
                'line': "'''single line"
            }
        ),
        (
            ["'''", "single line"],
            "'''\n   '''single line",  # missing closing quote
            0,
            0,
            FileParseError,
            {
                'reason': 'Invalid line',
                'line': "'''"
            }
        ),
        (
            ["", "another value"],  # multiline, but we forgot to close quotes
            "'''a\n#b",
            0,
            1,
            FileParseError,
            {
                'reason': "Multiline string not closed"
            }
        ),
        (
            ["", "c'''"],
            "'''a\n#b",
            0,
            1,
            None,
            ("'''a\n#b\nc'''", 1)
        ),
        (
            ["", "c'''"],  # multiline, but we forgot to close quotes
            "'''a\n#b",
            0,
            10000,  # no error. The function will stop before on the quotes
            None,
            ("'''a\n#b\nc'''", 1)
        ),
        (
            ["", "c", "hello", ""],  # quotes out of balance
            "'''a\n#b",
            0,
            3,
            FileParseError,
            {
                'reason': "Multiline string not closed"
            }
        ),
        (
            ["", "c", "hello", ""],
            "'''a\n#b",
            0,
            4,  # one too many
            IndexError,
            None
        ),
        (
            ["", "a'''c", "hello", ""],
            "'''a\n#b",
            0,
            3,
            FileParseError,
            {
                'reason': 'Invalid line',
                'line': "a'''c"
            }
        )
    ]
    return r


def test_file_parse_error():
    error = FileParseError(reason="No reason")
    assert str(error) == "No reason"

    error = FileParseError("", index=2)
    assert str(error) == (
        " (line 3)\n"
        "(line numbers match 'cylc view -p')"
    )

    error = FileParseError("", line="test")
    assert str(error) == ":\n   test"

    error = FileParseError("ERROR", lines={"a": ["1", "2"], "b": ["3"]})
    assert str(error) == '\n'.join([
        'ERROR',
        'File a',
        '  1',
        '  2\t<--',
        'File b',
        '  3\t<--'
    ])


def test_addsect():
    cfg = OrderedDictWithDefaults()
    cfg["section1"] = OrderedDictWithDefaults()
    cfg["section1"]["subsection"] = OrderedDictWithDefaults()
    new_section_name = "test"
    existing_section_name = "section1"
    parents = ["section1"]

    empty_cfg = OrderedDictWithDefaults()

    addsect(empty_cfg, "", [])
    assert len(empty_cfg) == 1
    assert "" in empty_cfg

    assert len(cfg) == 1
    addsect(cfg, existing_section_name, [])
    assert len(cfg) == 1

    assert "test" not in cfg["section1"]
    addsect(cfg, new_section_name, parents)
    assert len(cfg) == 1
    assert "test" in cfg["section1"]


def test_addict_error_line_already_encountered():
    with pytest.raises(FileParseError):
        addict({"title": "a"}, "title", None, ["title"], 1)


def test_addict_new_value_added():
    for key, val in [
        ('a', '1'),
        ('b', '2'),
        ('c', '3')
    ]:
        cfg = OrderedDictWithDefaults()
        addict(cfg, key, val, [], 0)
        assert key in cfg


def test_addict_replace_value():
    cfg = OrderedDictWithDefaults()
    cfg['country'] = 'ABC'
    addict(cfg, 'country', 'test', [], 0)
    assert cfg['country'] == 'test'


def test_addict_replace_value_1():
    """"Special case depending on key and parents, for

    - key is 'graph' AND parents['scheduling']['graph'] OR
    - len(parents)==3 AND parents['scheduling']['graph'][?]
    """

    # set 1 key is graph, parents is wrong (T, F)
    cfg = OrderedDictWithDefaults()
    cfg['graph'] = 'ABC'
    addict(cfg, 'graph', 'test', [], 0)
    assert cfg['graph'] == 'test'

    # set 2 key is graph, parents right (T, T)
    cfg = {
        'scheduling': {
            'graph': {
                'graph': 'ABC'
            }
        }
    }
    addict(cfg, 'graph', 'test', ['scheduling', 'graph'], 0)
    assert (
        cfg['scheduling']['graph']['graph']
    ) == ['ABC', 'test']

    # other side of boolean expression

    # set 3 len(parents) is 3, parents is wrong (T, F)
    cfg = {
        'scheduling': {
            'graph': {
                'team': {
                    'graph': 'ABC'
                }
            },
            'notme': {
                'team': {
                    'graph': '1'
                }
            }
        }
    }
    addict(cfg, 'graph', 'test', ['scheduling', 'notme', 'team'], 0)
    assert (
        cfg['scheduling']['notme']['team']['graph']
    ) == 'test'

    # set 3 len(parents) is 3, parents is right (T, T)
    cfg = {
        'scheduling': {
            'graph': {
                'team': {
                    'graph': 'ABC'
                }
            }
        }
    }
    addict(cfg, 'graph', 'test', ['scheduling', 'graph', 'team'], 0)
    assert cfg['scheduling']['graph']['team']['graph'] == ['ABC', 'test']


def test_multiline():
    for flines, value, index, maxline, exc, expected in get_multiline():
        if exc is not None:
            with pytest.raises(exc) as cm:
                multiline(flines, value, index, maxline)
            if isinstance(cm.value, FileParseError):
                exc = cm.value
                for key, attr in expected.items():
                    assert getattr(exc, key) == attr
        else:
            r = multiline(flines, value, index, maxline)
            assert r == expected


def test_read_and_proc_no_template_engine():
    with NamedTemporaryFile() as tf:
        fpath = tf.name
        template_vars = None
        viewcfg = {
            'empy': False, 'jinja2': False,
            'contin': False, 'inline': False
        }
        tf.write("a=b\n".encode())
        tf.flush()
        r = read_and_proc(fpath=fpath, template_vars=template_vars,
                          viewcfg=viewcfg)
        assert r == ['a=b']

        # last \\ is ignored, becoming just ''
        tf.write("c=\\\nd\n\\".encode())
        tf.flush()

        viewcfg = {
            'empy': False, 'jinja2': False,
            'contin': True, 'inline': False
        }
        r = read_and_proc(fpath=fpath, template_vars=template_vars,
                          viewcfg=viewcfg)
        assert r == ['a=b', 'c=d', '']


def test_inline():
    with NamedTemporaryFile() as tf:
        fpath = tf.name
        template_vars = None
        viewcfg = {
            'empy': False, 'jinja2': False,
            'contin': False, 'inline': True,
            'mark': None, 'single': None, 'label': None
        }
        with NamedTemporaryFile() as include_file:
            include_file.write("c=d".encode())
            include_file.flush()
            tf.write(("a=b\n%include \"{0}\""
                      .format(include_file.name)).encode())
            tf.flush()
            r = read_and_proc(fpath=fpath, template_vars=template_vars,
                              viewcfg=viewcfg)
            assert r == ['a=b', 'c=d']


def test_inline_error():
    with NamedTemporaryFile() as tf:
        fpath = tf.name
        template_vars = None
        viewcfg = {
            'empy': False, 'jinja2': False,
            'contin': False, 'inline': True,
            'mark': None, 'single': None, 'label': None
        }
        tf.write("a=b\n%include \"404.txt\"".encode())
        tf.flush()
        with pytest.raises(IncludeFileNotFoundError) as cm:
            read_and_proc(fpath=fpath, template_vars=template_vars,
                          viewcfg=viewcfg)
        assert "404.txt" in str(cm.value)


def test_read_and_proc_jinja2():
    with NamedTemporaryFile() as tf:
        fpath = tf.name
        template_vars = {
            'name': 'Cylc'
        }
        viewcfg = {
            'empy': False, 'jinja2': True,
            'contin': False, 'inline': False
        }
        tf.write("#!jinja2\na={{ name }}\n".encode())
        tf.flush()
        r = read_and_proc(fpath=fpath, template_vars=template_vars,
                          viewcfg=viewcfg)
        assert r == ['a=Cylc']


def test_read_and_proc_cwd(tmp_path):
    """The template processor should be able to read workflow files.

    This relies on moving to the config dir during file parsing.
    """

    sdir = tmp_path / "sub"
    sdir.mkdir()

    for sub in ["a", "b", "c"]:
        (sdir / sub).touch()

    viewcfg = {
        'empy': False,
        'jinja2': True,
        'contin': False,
        'inline': False
    }

    tmpf = tmp_path / "a.conf"

    with open(tmpf, 'w') as tf:
        tf.write(
            '#!Jinja2'
            '\n{% from "os" import listdir %}'
            '\n{% for f in listdir("sub") %}'
            '\n{{f}}'
            '\n{% endfor %}'
        )

    with open(tmpf, 'r') as tf:
        r = read_and_proc(fpath=tf.name, viewcfg=viewcfg)

    assert sorted(r) == ['a', 'b', 'c']


def test_read_and_proc_jinja2_error():
    with NamedTemporaryFile() as tf:
        fpath = tf.name
        template_vars = {
            'name': 'Cylc'
        }
        viewcfg = {
            'empy': False, 'jinja2': True,
            'contin': False, 'inline': False
        }
        tf.write("#!jinja2\na={{ name \n".encode())
        tf.flush()
        with pytest.raises(Jinja2Error) as cm:
            read_and_proc(fpath=fpath, template_vars=template_vars,
                          viewcfg=viewcfg)
        assert (
            "unexpected end of template, expected "
            "'end of print statement'."
        ) in str(cm.value)


def test_read_and_proc_jinja2_error_missing_shebang():
    with NamedTemporaryFile() as tf:
        fpath = tf.name
        template_vars = {
            'name': 'Cylc'
        }
        viewcfg = {
            'empy': False, 'jinja2': True,
            'contin': False, 'inline': False
        }
        # first line is missing shebang!
        tf.write("a={{ name }}\n".encode())
        tf.flush()
        r = read_and_proc(fpath=fpath, template_vars=template_vars,
                          viewcfg=viewcfg)
        assert r == ['a={{ name }}']


# --- originally we had a test for empy here, moved to test_empysupport

def test_parse_keys_only_singleline():
    with NamedTemporaryFile() as of, NamedTemporaryFile() as tf:
        fpath = tf.name
        template_vars = {
            'name': 'Cylc'
        }
        tf.write("#!jinja2\na={{ name }}\n".encode())
        tf.flush()
        r = parse(fpath=fpath, output_fname=of.name,
                  template_vars=template_vars)
        expected = OrderedDictWithDefaults()
        expected['a'] = 'Cylc'
        assert r == expected
        of.flush()
        output_file_contents = of.read().decode()
        assert output_file_contents == 'a=Cylc\n'


def test_parse_keys_only_multiline():
    with NamedTemporaryFile() as of, NamedTemporaryFile() as tf:
        fpath = tf.name
        template_vars = {
            'name': 'Cylc'
        }
        tf.write(
            "#!jinja2\na='''value is \\\n{{ name }}'''\n".encode())
        tf.flush()
        r = parse(fpath=fpath, output_fname=of.name,
                  template_vars=template_vars)
        expected = OrderedDictWithDefaults()
        expected['a'] = "'''value is Cylc'''"
        assert r == expected


def test_parse_invalid_line():
    with NamedTemporaryFile() as of, NamedTemporaryFile() as tf:
        fpath = tf.name
        template_vars = {
            'name': 'Cylc'
        }
        tf.write("#!jinja2\n{{ name }}\n".encode())
        tf.flush()
        with pytest.raises(FileParseError) as cm:
            parse(fpath=fpath, output_fname=of.name,
                  template_vars=template_vars)
        exc = cm.value
        assert exc.reason == 'Invalid line'
        assert exc.line_num == 1
        assert exc.line == 'Cylc'


def test_parse_comments():
    with NamedTemporaryFile() as of, NamedTemporaryFile() as tf:
        fpath = tf.name
        template_vars = {
            'name': 'Cylc'
        }
        tf.write("#!jinja2\na={{ name }}\n# comment!".encode())
        tf.flush()
        r = parse(fpath=fpath, output_fname=of.name,
                  template_vars=template_vars)
        expected = OrderedDictWithDefaults()
        expected['a'] = 'Cylc'
        assert r == expected
        of.flush()
        output_file_contents = of.read().decode()
        assert output_file_contents == 'a=Cylc\n# comment!\n'


def test_parse_with_sections():
    with NamedTemporaryFile() as of, NamedTemporaryFile() as tf:
        fpath = tf.name
        template_vars = {
            'name': 'Cylc'
        }
        tf.write(("#!jinja2\n[section1]\n"
                  "a={{ name }}\n# comment!\n"
                  "[[subsection1]]\n"
                  "[[subsection2]]\n"
                  "[section2]").encode())
        tf.flush()
        r = parse(fpath=fpath, output_fname=of.name,
                  template_vars=template_vars)
        expected = OrderedDictWithDefaults()
        expected['section1'] = OrderedDictWithDefaults()
        expected['section1']['a'] = 'Cylc'
        expected['section1']['subsection1'] = OrderedDictWithDefaults()
        expected['section1']['subsection2'] = OrderedDictWithDefaults()
        expected['section2'] = OrderedDictWithDefaults()
        assert r == expected
        of.flush()
        output_file_contents = of.read().decode()
        assert output_file_contents == (
            '[section1]\na=Cylc\n# comment!\n'
            '[[subsection1]]\n'
            '[[subsection2]]\n'
            '[section2]\n'
        )


def test_parse_with_sections_missing_bracket():
    with NamedTemporaryFile() as tf:
        fpath = tf.name
        template_vars = {
            'name': 'Cylc'
        }
        tf.write(
            "#!jinja2\n[[section1]\na={{ name }}\n# comment!".encode())
        tf.flush()
        with pytest.raises(FileParseError) as cm:
            parse(fpath=fpath, output_fname="",
                  template_vars=template_vars)
        exc = cm.value
        assert exc.reason == 'bracket mismatch'
        assert exc.line == '[[section1]'


def test_parse_with_sections_error_wrong_level():
    with NamedTemporaryFile() as of, NamedTemporaryFile() as tf:
        fpath = tf.name
        template_vars = {
            'name': 'Cylc'
        }
        tf.write(("#!jinja2\n[section1]\n"
                  "a={{ name }}\n# comment!\n"
                  "[[[subsection1]]]\n")  # expected [[]] instead!
                 .encode())
        tf.flush()
        with pytest.raises(FileParseError) as cm:
            parse(fpath=fpath, output_fname=of.name,
                  template_vars=template_vars)
        exc = cm.value
        assert exc.line_num == 4
        assert exc.line == '[[[subsection1]]]'


def test_unclosed_multiline():
    with NamedTemporaryFile() as tf:
        fpath = tf.name
        template_vars = {
            'name': 'Cylc'
        }
        tf.write(('''
        [scheduling]
            [[graph]]
                R1 = """
                    foo

        [runtime]
            [[foo]]
                script = """
                    echo hello world
                """
        ''').encode())
        tf.flush()
        with pytest.raises(FileParseError) as cm:
            parse(fpath=fpath, output_fname="",
                  template_vars=template_vars)
        exc = cm.value
        assert exc.reason == 'Invalid line'
        assert 'echo hello world' in exc.line
        assert 'Did you forget to close [scheduling][graph]R1?' in str(exc)


@pytest.mark.parametrize(
    'expect, native_tvars, plugin_result, log',
    [
        pytest.param(
            {'FOO': 123},
            {'FOO': 123},
            {
                'templating_detected': None,
                'template_variables': {'FOO': 122}
            },
            [],
            id='no templating engine set'
        ),
        pytest.param(
            {'FOO': 125},
            {'FOO': 125},
            {
                'templating_detected': 'qux',
                'template_variables': {'FOO': 124}
            },
            ['Overriding FOO: 124 -> 125'],
            id='Variable overridden'
        ),
        pytest.param(
            {'FOO': 126},
            {'FOO': 126},
            {
                'templating_detected': 'qux',
                'template_variables': {'FOO': 126}
            },
            [],
            id='Variable overridden quietly'
        )
    ]
)
def test_merge_template_vars(caplog, expect, native_tvars, plugin_result, log):
    assert merge_template_vars(native_tvars, plugin_result) == expect
    assert [r.msg for r in caplog.records] == log


@pytest.fixture
def _mock_old_template_vars_db(tmp_path):
    def _inner(create_srclink=True):
        # Create a fake workflow dir:
        (tmp_path / 'flow.cylc').touch()
        (tmp_path / 'log').mkdir()
        db_path = tmp_path / 'log/db'
        db_path.touch()

        # Set up a fake workflow database:
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "CREATE TABLE workflow_template_vars"
            "(key TEXT, value TEXT, PRIMARY KEY(key)) ;"
        )
        conn.execute(
            "INSERT INTO workflow_template_vars VALUES"
            "    ('Marius', '\"Consul\"')"
        )
        conn.execute(
            "CREATE TABLE workflow_params"
            "(key TEXT, value TEXT, PRIMARY KEY(key)) ;"
        )
        conn.execute(
            "INSERT INTO workflow_params VALUES"
            f"    ('cylc_version', '{cylc_version}')"
        )
        conn.commit()
        conn.close()

        # Simulate being an installed rundir by creating a sourcelink:
        if create_srclink:
            src = (tmp_path / 'src')
            src.mkdir(exist_ok=True)
            link = tmp_path.parent / '_cylc-install/source'
            link.parent.mkdir(exist_ok=True)
            with suppress(FileExistsError):
                # We don't mind the link persisting.
                os.symlink(src, link)
        return tmp_path / 'flow.cylc'
    yield _inner


@pytest.mark.parametrize(
    'expect, tvars',
    [
        param(
            {'Marius': 'Consul', 'Julius': 'Pontifex'}, {'Julius': 'Pontifex'},
            id='It adds a new key at the end'
        ),
        param(
            {'Marius': 'Tribune'}, {'Marius': 'Tribune'},
            id='It overrides an existing key'
        ),
    ]
)
def test__prepend_old_templatevars(_mock_old_template_vars_db, expect, tvars):
    # Create a target for a source symlink
    result = _prepend_old_templatevars(
        _mock_old_template_vars_db(), tvars)
    assert result == expect


def test_get_fpath_for_source(tmp_path):
    # Create rundir and srcdir:
    srcdir = tmp_path / 'source'
    rundir = tmp_path / 'run'
    srcdir.mkdir()
    rundir.mkdir()
    (rundir / 'flow.cylc').touch()
    (srcdir / 'flow.cylc').touch()

    # Mock Options object:
    opts = SimpleNamespace()

    # It raises an error if source is not linked:
    with pytest.raises(
        ParsecError, match=f'Cannot validate {rundir} against source:'
    ):
        opts.against_source = True
        _get_fpath_for_source(rundir / 'flow.cylc', opts)

    # Create symlinks:
    link = rundir / '_cylc-install/source'
    link.parent.mkdir(exist_ok=True)
    os.symlink(srcdir, link)

    # It does nothing if opts.against_source is False:
    opts.against_source = False
    assert _get_fpath_for_source(
        rundir / 'flow.cylc', opts) == rundir / 'flow.cylc'

    # It gets source dir if opts.against_source is True:
    opts.against_source = True
    assert _get_fpath_for_source(
        rundir / 'flow.cylc', opts) == str(srcdir / 'flow.cylc')

def test_user_has_no_cwd(tmp_path):
    """Test we can parse a config file even if cwd does not exist."""
    cwd = tmp_path/"cwd"
    os.mkdir(cwd)
    os.chdir(cwd)
    os.rmdir(cwd)
    # (I am now located in a non-existent directory. Outrageous!)
    with NamedTemporaryFile() as tf:
        fpath = tf.name
        tf.write(('''
        [scheduling]
            [[graph]]
                R1 = "foo"
        ''').encode())
        tf.flush()
        # Should not raise FileNotFoundError from os.getcwd():
        parse(fpath=fpath, output_fname="")
