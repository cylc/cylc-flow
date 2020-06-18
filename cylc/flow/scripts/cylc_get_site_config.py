#!/usr/bin/env python3

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

"""cylc [admin] get-site-config [OPTIONS]

Print cylc site/user configuration settings.

By default all settings are printed. For specific sections or items
use -i/--item and wrap parent sections in square brackets:
   cylc get-site-config --item '[editors]terminal'
Multiple items can be specified at once."""

from cylc.flow.cfgspec.glbl_cfg import glbl_cfg
from cylc.flow.option_parsers import CylcOptionParser as COP
from cylc.flow.terminal import cli_function
from cylc.flow.platforms import forward_lookup


def get_option_parser():
    parser = COP(__doc__, argdoc=[])

    parser.add_option(
        "-i", "--item", metavar="[SEC...]ITEM",
        help="Item or section to print (multiple use allowed).",
        action="append", dest="item", default=[])

    parser.add_option(
        "--sparse",
        help="Only print items explicitly set in the config files.",
        action="store_true", default=False, dest="sparse")

    parser.add_option(
        "-p", "--python",
        help="Print native Python format.",
        action="store_true", default=False, dest="pnative")

    parser.add_option(
        "--print-run-dir",
        help="Print the configured top level run directory.",
        action="store_true", default=False, dest="run_dir")

    parser.add_option(
        "--print-site-dir",
        help="Print the site configuration directory location.",
        action="store_true", default=False, dest="site_dir")

    parser.add_option(
        "--print-user-dir",
        help="Print the user configuration directory location.",
        action="store_true", default=False, dest="user_dir")

    return parser


@cli_function(get_option_parser, remove_opts=['--host', '--user'])
def main(parser, options):
    if options.run_dir:
        print(forward_lookup()['run directory'])
    elif options.site_dir:
        print(glbl_cfg().SITE_CONF_DIR)
    elif options.user_dir:
        print(glbl_cfg().USER_CONF_DIR)
    else:
        glbl_cfg().idump(
            options.item, sparse=options.sparse, pnative=options.pnative)


if __name__ == "__main__":
    main()
