# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
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

import unittest

from cylc.flow.parsec.util import *


class TestUtil(unittest.TestCase):

    # --- listjoin

    def test_listjoin(self):
        self.assertEqual('', listjoin(None))
        self.assertEqual('test', listjoin(None, 'test'))
        self.assertEqual('test', listjoin([], 'test'))
        self.assertEqual('test', listjoin([None], 'test'))
        self.assertEqual('test, test', listjoin(['test', 'test']))
        self.assertEqual('\'test,\', test', listjoin(['test,', 'test']))

    # --- printcfg

    def test_printcfg(self):
        cfg = OrderedDictWithDefaults()
        cfg['root'] = OrderedDictWithDefaults()
        cfg['root']['special'] = 1
        cfg['root']['normal'] = 0
        cfg['root'][None] = None
        cfg[None] = None

        myhandle = StringIO()
        printcfg(cfg, handle=myhandle)
        expected = "\n[root]\n    special = 1\n    normal = 0\n    \n"
        actual = myhandle.getvalue()
        self.assertEqual(expected, actual)

    def test_printcfg_none_str_is_none(self):
        cfg = OrderedDictWithDefaults()
        cfg['root'] = OrderedDictWithDefaults()
        cfg['root']['special'] = 1
        cfg['root']['normal'] = 0
        cfg['root'][None] = None
        cfg[None] = None

        myhandle = StringIO()
        printcfg(cfg, handle=myhandle, none_str=None)
        expected = "[root]\n    special = 1\n    normal = 0\n"
        actual = myhandle.getvalue()
        self.assertEqual(expected, actual)

    def test_printcfg_list_values(self):
        cfg = OrderedDictWithDefaults()
        cfg['root'] = OrderedDictWithDefaults()
        cfg['root']['special'] = ['a', 'b', 'c', None]
        cfg['root']['normal'] = 0

        myhandle = StringIO()
        printcfg(cfg, handle=myhandle, none_str='d')
        expected = "[root]\n    special = a, b, c, d\n    normal = 0\n"
        actual = myhandle.getvalue()
        self.assertEqual(expected, actual)

    def test_printcfg_break_lines(self):
        cfg = OrderedDictWithDefaults()
        cfg['root'] = OrderedDictWithDefaults()
        cfg['root']['special'] = "\nthis is\nvalid"
        cfg['root']['normal'] = 0

        myhandle = StringIO()
        printcfg(cfg, handle=myhandle)
        expected = "[root]\n    special = \"\"\"\n        \n    " \
                   "    this is\n        valid\n    \"\"\"\n    normal = 0\n"
        actual = myhandle.getvalue()
        self.assertEqual(expected, actual)

    # --- replicate

    def test_replicate(self):
        replicate('Name', None)  # does nothing, no exception/error
        source_1 = OrderedDictWithDefaults()
        source_1["name"] = "sea"
        source_1["origin"] = "kitchen"
        source_1.defaults_ = {"brewery": False}
        source_2 = OrderedDictWithDefaults()
        source_2["name"] = ["sea", "legume"]
        source_2["origin"] = "fridge"
        source_3 = OrderedDictWithDefaults()
        source_3["name"] = OrderedDictWithDefaults()
        source_3["name"]["value"] = "oil"
        source_3["name"]["key"] = 1
        source_3["name"].defaults_ = {"value": 1}

        target_1 = OrderedDictWithDefaults()
        target_2 = OrderedDictWithDefaults()
        target_3 = OrderedDictWithDefaults()

        replicate(target_1, source_1)
        replicate(target_2, source_2)
        replicate(target_3, source_3)

        # Note: assertDictEqual not available for Python 2.6
        self.assertEqual(str(source_1), str(target_1))
        self.assertEqual(str(source_2), str(target_2))
        self.assertEqual(str(source_3), str(target_3))

    # --- pdeepcopy

    def test_pdeepcopy(self):
        """This is tested entirely by the tests in replicate as well"""
        source = OrderedDictWithDefaults()
        source["name"] = OrderedDictWithDefaults()
        source["name"]["value"] = "oil"
        source["name"]["key"] = 1
        source["name"].defaults_ = {"value": 1}

        target = pdeepcopy(source)

        self.assertEqual(source, target)

    # --- poverride

    def test_poverride_append(self):
        source = OrderedDictWithDefaults()
        source["name"] = OrderedDictWithDefaults()
        source["name"]["value"] = "oil"
        source["name"]["key"] = [1, 2, 3, 4]

        target = OrderedDictWithDefaults()
        target["name"] = OrderedDictWithDefaults()
        target["name"]["index"] = 0
        poverride(target, None)  # harmless, and no error/exception

        poverride(target, source)

        expected = OrderedDictWithDefaults()
        expected["index"] = 0
        expected["value"] = "oil"
        expected["key"] = [1, 2, 3, 4]

        self.assertEqual(expected, target["name"], )

    def test_poverride_prepend(self):
        source = OrderedDictWithDefaults()
        source["name"] = OrderedDictWithDefaults()
        source["name"]["value"] = "oil"
        source["name"]["key"] = [1, 2, 3, 4]

        target = OrderedDictWithDefaults()
        target["name"] = OrderedDictWithDefaults()
        target["name"]["index"] = 0
        poverride(target, None)  # harmless, and no error/exception

        poverride(target, source, prepend=True)

        expected = OrderedDictWithDefaults()
        expected["key"] = [1, 2, 3, 4]
        expected["value"] = "oil"
        expected["index"] = 0

        self.assertEqual(expected, target["name"])

    # -- m_override

    def test_m_override(self):
        source = OrderedDictWithDefaults()
        source["name"] = OrderedDictWithDefaults()
        source["name"]["index"] = "oil"
        source["name2"] = OrderedDictWithDefaults()
        source["name2"]["key"] = [1, 2, 3, 4]
        source["name2"]["text"] = ""
        source["name2"]["subdict"] = OrderedDictWithDefaults()
        source["name2"]["subdict"]['family'] = 'ALL'

        target = OrderedDictWithDefaults()
        target["name"] = OrderedDictWithDefaults()
        target["name"]["index"] = 0
        target['__MANY__'] = OrderedDictWithDefaults()
        target['__MANY__']['name2'] = OrderedDictWithDefaults()
        target['__MANY__']['subdict'] = OrderedDictWithDefaults()
        target['__MANY__']['subdict']['__MANY__'] = OrderedDictWithDefaults()
        target['__MANY__']['subdict']['__MANY__']['family'] = 'LATIN'
        target['__MANY__']['key'] = []
        target['__MANY__']['text'] = "Ad infinitum"

        self.assertEqual(0, target["name"]["index"])
        m_override(target, source)
        self.assertEqual("oil", target["name"]["index"])

    def test_m_override_many_with_many(self):
        source = OrderedDictWithDefaults()
        source["name"] = OrderedDictWithDefaults()
        source["name"]["index"] = "oil"
        source["name2"] = OrderedDictWithDefaults()
        source["name2"]["key"] = [1, 2, 3, 4]
        source["name2"]["text"] = ""
        source["name2"]["subdict"] = OrderedDictWithDefaults()
        source["name2"]["subdict"]['family'] = 'ALL'

        target = OrderedDictWithDefaults()
        target["name"] = OrderedDictWithDefaults()
        target["name"]["index"] = 0
        target['__MANY__'] = OrderedDictWithDefaults()
        target['__MANY__']['name2'] = OrderedDictWithDefaults()
        target['__MANY__']['subdict'] = OrderedDictWithDefaults()
        target['__MANY__']['subdict']['__MANY__'] = OrderedDictWithDefaults()
        target['__MANY__']['subdict']['__MANY__']['family'] = 'LATIN'
        target['__MANY__']['key'] = []
        target['__MANY__']['text'] = "Ad infinitum"

        # code is OK until here

        # It appears this is valid for now, but may change later
        target['__MANY__']['__MANY__'] = OrderedDictWithDefaults()

        with self.assertRaises(Exception):
            m_override(target, source)

    def test_m_override_without_many_1(self):
        source = OrderedDictWithDefaults()
        source["name"] = OrderedDictWithDefaults()
        source["name"]["value"] = "oil"
        source["name"]["key"] = [1, 2, 3, 4]

        target = OrderedDictWithDefaults()
        target["name"] = OrderedDictWithDefaults()
        target["name"]["index"] = 0

        with self.assertRaises(Exception):
            m_override(target, source)

    def test_m_override_without_many_2(self):
        source = OrderedDictWithDefaults()
        source["name"] = OrderedDictWithDefaults()
        source["name"]["index"] = "oil"
        source["name2"] = OrderedDictWithDefaults()
        source["name2"]["key"] = [1, 2, 3, 4]

        target = OrderedDictWithDefaults()
        target["name"] = OrderedDictWithDefaults()
        target["name"]["index"] = 0
        target['__MANY__'] = OrderedDictWithDefaults()
        target['__MANY__']['name2'] = OrderedDictWithDefaults()
        # target['__MANY__']['key'] = []

        with self.assertRaises(Exception):
            m_override(target, source)

    def test_m_override_without_many_3(self):
        source = OrderedDictWithDefaults()
        source["name"] = OrderedDictWithDefaults()
        source["name"]["index"] = "oil"
        source["name2"] = OrderedDictWithDefaults()
        source["name2"]["key"] = [1, 2, 3, 4]
        source["name2"]["text"] = ""
        source["name2"]["subdict"] = OrderedDictWithDefaults()
        source["name2"]["subdict"]['family'] = 'ALL'

        target = OrderedDictWithDefaults()
        target["name"] = OrderedDictWithDefaults()
        target["name"]["index"] = 0
        target['__MANY__'] = OrderedDictWithDefaults()
        target['__MANY__']['name2'] = OrderedDictWithDefaults()
        target['__MANY__']['subdict'] = OrderedDictWithDefaults()
        target['__MANY__']['key'] = []
        target['__MANY__']['text'] = "Ad infinitum"

        with self.assertRaises(Exception):
            m_override(target, source)

    def test_m_override_without_many_4(self):
        source = OrderedDictWithDefaults()
        source["name"] = OrderedDictWithDefaults()
        source["name"]["index"] = "oil"
        source["name2"] = OrderedDictWithDefaults()
        source["name2"]["key"] = [1, 2, 3, 4]
        source["name2"]["text"] = ""
        source["name2"]["subdict"] = OrderedDictWithDefaults()
        source["name2"]["subdict"]['family'] = 'ALL'

        target = OrderedDictWithDefaults()
        target["name"] = OrderedDictWithDefaults()
        target["name"]["index"] = 0
        target['__MANY__'] = OrderedDictWithDefaults()
        target['__MANY__']['name2'] = OrderedDictWithDefaults()
        target['__MANY__']['key'] = []
        target['__MANY__']['text'] = "Ad infinitum"

        with self.assertRaises(Exception):
            m_override(target, source)

    # --- un_many

    def test_un_many(self):
        target = OrderedDictWithDefaults()
        target["name"] = OrderedDictWithDefaults()
        target["name"]["index"] = 0
        target['__MANY__'] = OrderedDictWithDefaults()
        target['__MANY__']['name2'] = OrderedDictWithDefaults()
        target['__MANY__']['subdict'] = OrderedDictWithDefaults()
        target['__MANY__']['key'] = []
        target['__MANY__']['text'] = "Ad infinitum"

        un_many(None)  # harmless, no error/exception

        un_many(target)

        self.assertFalse('__MANY__' in list(target))

    def test_un_many_keyerror(self):
        """
        Only way that this may happen is if dict is updated elsewhere.
        """
        class MyODWD(OrderedDictWithDefaults):
            def __delitem__(self, _):
                raise KeyError()

        target = MyODWD()
        target["name"] = "Anything"
        target.defaults_ = dict()
        target.defaults_["name"] = True
        target.defaults_["__MANY__"] = True
        target['__MANY__'] = MyODWD()
        target['__MANY__']['name2'] = MyODWD()
        target['__MANY__']['subdict'] = MyODWD()
        target['__MANY__']['key'] = []
        target['__MANY__']['text'] = "Ad infinitum"

        un_many(None)  # harmless, no error/exception
        un_many(target)

        self.assertTrue('__MANY__' in target, target)

    def test_un_many_keyerror_no_default(self):
        """
        Only way that this may happen is if dict is updated elsewhere.

        And in this case, when there is no defaults_, the API raises the
        current KeyError.
        """
        class MyODWD(OrderedDictWithDefaults):
            def __delitem__(self, _):
                raise KeyError()

        target = MyODWD()
        target["name"] = "Anything"
        target['__MANY__'] = MyODWD()
        target['__MANY__']['name2'] = MyODWD()
        target['__MANY__']['subdict'] = MyODWD()
        target['__MANY__']['key'] = []
        target['__MANY__']['text'] = "Ad infinitum"

        un_many(None)  # harmless, no error/exception

        with self.assertRaises(KeyError):
            un_many(target)

    # --- itemstr

    def test_itemstr(self):
        parents = ["parent1", "parent2"]
        text = itemstr(parents=parents, item="Value", value="Anything")
        self.assertEqual('[parent1][parent2]Value = Anything', text)

    def test_itemstr_no_item(self):
        parents = ["parent1", "parent2", "Value"]
        text = itemstr(parents=parents, item=None, value="Anything")
        self.assertEqual('[parent1][parent2]Value = Anything', text)

    def test_itemstr_no_parents_no_item(self):
        text = itemstr(parents=None, item=None, value='Anything')
        self.assertEqual('Anything', text)

    def test_itemstr_no_parents(self):
        text = itemstr(parents=None, item="Value", value='Anything')
        self.assertEqual('Value = Anything', text)

    def test_itemstr_no_parents_no_value(self):
        text = itemstr(parents=None, item="Value", value=None)
        self.assertEqual('Value', text)


if __name__ == '__main__':
    unittest.main()
