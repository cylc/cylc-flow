#!/usr/bin/env python3

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2019 NIWA & British Crown (Met Office) & Contributors.
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

import tempfile
import unittest

from parsec.fileparse import *


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
            "FileParseError:\nMultiline string not closed:\n   '''single line"
        ),
        (
            ["'''", "single line"],
            "'''\n   '''single line",  # missing closing quote
            0,
            0,
            FileParseError,
            "FileParseError:\nInvalid line:\n   '''"
        ),
        (
            ["", "another value"],  # multiline, but we forgot to close quotes
            "'''a\n#b",
            0,
            1,
            FileParseError,
            "FileParseError:\nMultiline string not closed"
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
            "FileParseError:\nMultiline string not closed"
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
            "FileParseError:\nInvalid line:\n   a'''c"
        )
    ]
    return r


class TestFileparse(unittest.TestCase):

    def test_file_parse_error(self):
        error = FileParseError(reason="No reason")
        self.assertEqual("FileParseError:\nNo reason", error.msg)

        error = FileParseError("", index=2)
        self.assertEqual("FileParseError:\n (line 3)\n"
                         "(line numbers match 'cylc view -p')", error.msg)

        error = FileParseError("", line="test")
        self.assertEqual("FileParseError:\n:\n   test", error.msg)

        error = FileParseError("", lines=["a", "b"])
        self.assertEqual("FileParseError:\n\nContext lines:\n"
                         "a\nb	<-- FileParseError", error.msg)

    def test_addsect(self):
        cfg = OrderedDictWithDefaults()
        cfg["section1"] = OrderedDictWithDefaults()
        cfg["section1"]["subsection"] = OrderedDictWithDefaults()
        new_section_name = "test"
        existing_section_name = "section1"
        parents = ["section1"]

        empty_cfg = OrderedDictWithDefaults()

        addsect(empty_cfg, "", [])
        self.assertTrue(len(empty_cfg) == 1)
        self.assertTrue("" in empty_cfg)

        self.assertTrue(len(cfg) == 1)
        addsect(cfg, existing_section_name, [])
        self.assertTrue(len(cfg) == 1)

        self.assertTrue("test" not in cfg["section1"])
        addsect(cfg, new_section_name, parents)
        self.assertTrue(len(cfg) == 1)
        self.assertTrue("test" in cfg["section1"])

    def test_addict_error_line_already_encountered(self):
        with self.assertRaises(FileParseError):
            addict({"title": "a"}, "title", None, ["title"], 1)

    def test_addict_new_value_added(self):
        for key, val in [
            ('a', '1'),
            ('b', '2'),
            ('c', '3')
        ]:
            cfg = OrderedDictWithDefaults()
            addict(cfg, key, val, [], 0)
            self.assertTrue(key in cfg)

    def test_addict_replace_value(self):
        cfg = OrderedDictWithDefaults()
        cfg['country'] = 'ABC'
        addict(cfg, 'country', 'test', [], 0)
        self.assertEqual('test', cfg['country'])

    def test_addict_replace_value_1(self):
        """"Special case depending on key and parents, for

        - key is 'graph' AND parents['scheduling']['dependencies'] OR
        - len(parents)==3 AND parents['scheduling']['dependencies'][?]
        """

        # set 1 key is graph, parents is wrong (T, F)
        cfg = OrderedDictWithDefaults()
        cfg['graph'] = 'ABC'
        addict(cfg, 'graph', 'test', [], 0)
        self.assertEqual('test', cfg['graph'])

        # set 2 key is graph, parents right (T, T)
        cfg = {
            'scheduling': {
                'dependencies': {
                    'graph': 'ABC'
                }
            }
        }
        addict(cfg, 'graph', 'test', ['scheduling', 'dependencies'], 0)
        self.assertEqual(['ABC', 'test'],
                         cfg['scheduling']['dependencies']['graph'])

        # other side of boolean expression

        # set 3 len(parents) is 3, parents is wrong (T, F)
        cfg = {
            'scheduling': {
                'dependencies': {
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
        self.assertEqual('test',
                         cfg['scheduling']['notme']['team']['graph'])

        # set 3 len(parents) is 3, parents is right (T, T)
        cfg = {
            'scheduling': {
                'dependencies': {
                    'team': {
                        'graph': 'ABC'
                    }
                }
            }
        }
        addict(cfg, 'graph', 'test', ['scheduling', 'dependencies', 'team'], 0)
        self.assertEqual(['ABC', 'test'],
                         cfg['scheduling']['dependencies']['team']['graph'])

    def test_multiline(self):
        for flines, value, index, maxline, exc, expected in get_multiline():
            if exc is not None:
                with self.assertRaises(exc) as cm:
                    multiline(flines, value, index, maxline)
                if isinstance(cm.exception, FileParseError):
                    self.assertEqual(expected, cm.exception.msg)
            else:
                r = multiline(flines, value, index, maxline)
                self.assertEqual(expected, r)

    def test_read_and_proc_no_template_engine(self):
        with tempfile.NamedTemporaryFile() as tf:
            fpath = tf.name
            template_vars = None
            viewcfg = {
                'empy': False, 'jinja2': False,
                'contin': False, 'inline': False
            }
            asedit = None
            tf.write("a=b\n".encode())
            tf.flush()
            r = read_and_proc(fpath=fpath, template_vars=template_vars,
                              viewcfg=viewcfg, asedit=asedit)
            self.assertEqual(['a=b'], r)

            # last \\ is ignored, becoming just ''
            tf.write("c=\\\nd\n\\".encode())
            tf.flush()

            viewcfg = {
                'empy': False, 'jinja2': False,
                'contin': True, 'inline': False
            }
            r = read_and_proc(fpath=fpath, template_vars=template_vars,
                              viewcfg=viewcfg, asedit=asedit)
            self.assertEqual(['a=b', 'c=d', ''], r)

    def test_inline(self):
        with tempfile.NamedTemporaryFile() as tf:
            fpath = tf.name
            template_vars = None
            viewcfg = {
                'empy': False, 'jinja2': False,
                'contin': False, 'inline': True,
                'mark': None, 'single': None, 'label': None
            }
            asedit = None
            with tempfile.NamedTemporaryFile() as include_file:
                include_file.write("c=d".encode())
                include_file.flush()
                tf.write(("a=b\n%include \"{0}\""
                          .format(include_file.name)).encode())
                tf.flush()
                r = read_and_proc(fpath=fpath, template_vars=template_vars,
                                  viewcfg=viewcfg, asedit=asedit)
                self.assertEqual(['a=b', 'c=d'], r)

    def test_inline_error(self):
        with tempfile.NamedTemporaryFile() as tf:
            fpath = tf.name
            template_vars = None
            viewcfg = {
                'empy': False, 'jinja2': False,
                'contin': False, 'inline': True,
                'mark': None, 'single': None, 'label': None
            }
            asedit = None
            tf.write("a=b\n%include \"404.txt\"".encode())
            tf.flush()
            with self.assertRaises(FileParseError) as cm:
                read_and_proc(fpath=fpath, template_vars=template_vars,
                              viewcfg=viewcfg, asedit=asedit)
            self.assertTrue("Include-file not found: 404.txt"
                            in cm.exception.msg)

    def test_read_and_proc_jinja2(self):
        with tempfile.NamedTemporaryFile() as tf:
            fpath = tf.name
            template_vars = {
                'name': 'Cylc'
            }
            viewcfg = {
                'empy': False, 'jinja2': True,
                'contin': False, 'inline': False
            }
            asedit = None
            tf.write("#!jinja2\na={{ name }}\n".encode())
            tf.flush()
            r = read_and_proc(fpath=fpath, template_vars=template_vars,
                              viewcfg=viewcfg, asedit=asedit)
            self.assertEqual(['a=Cylc'], r)

    def test_read_and_proc_jinja2_error(self):
        with tempfile.NamedTemporaryFile() as tf:
            fpath = tf.name
            template_vars = {
                'name': 'Cylc'
            }
            viewcfg = {
                'empy': False, 'jinja2': True,
                'contin': False, 'inline': False
            }
            asedit = None
            tf.write("#!jinja2\na={{ name \n".encode())
            tf.flush()
            with self.assertRaises(FileParseError) as cm:
                read_and_proc(fpath=fpath, template_vars=template_vars,
                              viewcfg=viewcfg, asedit=asedit)
            self.assertTrue("TemplateSyntaxError: unexpected end of "
                            "template, expected 'end of print statement'."
                            in cm.exception.msg)

    def test_read_and_proc_jinja2_error_missing_shebang(self):
        with tempfile.NamedTemporaryFile() as tf:
            fpath = tf.name
            template_vars = {
                'name': 'Cylc'
            }
            viewcfg = {
                'empy': False, 'jinja2': True,
                'contin': False, 'inline': False
            }
            asedit = None
            # first line is missing shebang!
            tf.write("a={{ name }}\n".encode())
            tf.flush()
            r = read_and_proc(fpath=fpath, template_vars=template_vars,
                              viewcfg=viewcfg, asedit=asedit)
            self.assertEqual(['a={{ name }}'], r)

    # --- originally we had a test for empy here, moved to test_empysupport

    def test_parse_keys_only_singleline(self):
        with tempfile.NamedTemporaryFile() as of:
            with tempfile.NamedTemporaryFile() as tf:
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
                self.assertEqual(expected, r)
                of.flush()
                output_file_contents = of.read().decode()
                self.assertEqual('a=Cylc\n', output_file_contents)

    def test_parse_keys_only_multiline(self):
        with tempfile.NamedTemporaryFile() as of:
            with tempfile.NamedTemporaryFile() as tf:
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
                self.assertEqual(expected, r)

    def test_parse_invalid_line(self):
        with tempfile.NamedTemporaryFile() as of:
            with tempfile.NamedTemporaryFile() as tf:
                fpath = tf.name
                template_vars = {
                    'name': 'Cylc'
                }
                tf.write("#!jinja2\n{{ name }}\n".encode())
                tf.flush()
                with self.assertRaises(FileParseError) as cm:
                    parse(fpath=fpath, output_fname=of.name,
                          template_vars=template_vars)
                self.assertTrue("Invalid line 1: Cylc" in cm.exception.msg)

    def test_parse_comments(self):
        with tempfile.NamedTemporaryFile() as of:
            with tempfile.NamedTemporaryFile() as tf:
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
                self.assertEqual(expected, r)
                of.flush()
                output_file_contents = of.read().decode()
                self.assertEqual('a=Cylc\n# comment!\n', output_file_contents)

    def test_parse_with_sections(self):
        with tempfile.NamedTemporaryFile() as of:
            with tempfile.NamedTemporaryFile() as tf:
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
                self.assertEqual(expected, r)
                of.flush()
                output_file_contents = of.read().decode()
                self.assertEqual('[section1]\na=Cylc\n# comment!\n'
                                 '[[subsection1]]\n'
                                 '[[subsection2]]\n'
                                 '[section2]\n',
                                 output_file_contents)

    def test_parse_with_sections_missing_bracket(self):
        with tempfile.NamedTemporaryFile() as tf:
            fpath = tf.name
            template_vars = {
                'name': 'Cylc'
            }
            tf.write(
                "#!jinja2\n[[section1]\na={{ name }}\n# comment!".encode())
            tf.flush()
            with self.assertRaises(FileParseError) as cm:
                parse(fpath=fpath, output_fname="",
                      template_vars=template_vars)
            self.assertTrue("bracket mismatch" in cm.exception.msg)

    def test_parse_with_sections_error_wrong_level(self):
        with tempfile.NamedTemporaryFile() as of:
            with tempfile.NamedTemporaryFile() as tf:
                fpath = tf.name
                template_vars = {
                    'name': 'Cylc'
                }
                tf.write(("#!jinja2\n[section1]\n"
                          "a={{ name }}\n# comment!\n"
                          "[[[subsection1]]]\n")  # expected [[]] instead!
                         .encode())
                tf.flush()
                with self.assertRaises(FileParseError) as cm:
                    parse(fpath=fpath, output_fname=of.name,
                          template_vars=template_vars)
                self.assertEqual("FileParseError:\nError line 4: "
                                 "[[[subsection1]]]", cm.exception.msg)


if __name__ == '__main__':
    unittest.main()
