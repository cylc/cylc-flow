#!/usr/bin/env python

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2017 NIWA
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

import gtk
from copy import deepcopy

from cylc.task_state import TASK_STATUSES_ORDERED
from cylc.config import SuiteConfig
from cylc.task_id import TaskID

empty = {}
empty['small'] = ["16 16 1 1", ". c None"]
empty['small'].extend(["................"] * 16)
empty['medium'] = ["22 22 1 1", ". c None"]
empty['medium'].extend(["......................"] * 22)
empty['large'] = ["27 27 1 1", ". c None"]
empty['large'].extend(["..........................."] * 27)
empty['extra large'] = ["37 37 1 1", ". c None"]
empty['extra large'].extend(["....................................."] * 37)

# A small square for [visualization] color indicators.
visdot = [
    "10 10 2 1",
    "o c <BRDR>",
    ". c <VISC>",
    "oooooooooo",
    "o........o",
    "o........o",
    "o........o",
    "o........o",
    "o........o",
    "o........o",
    "o........o",
    "o........o",
    "oooooooooo",
]

stopped = {
    'small': [
        "10 10 3 1",
        ". c <FILL>",
        "* c <BRDR>",
        "+ c None",
        "+++++*****",
        "+++++*****",
        "+++++...**",
        "+++++...**",
        "+++++...**",
        "**...+++++",
        "**...+++++",
        "**...+++++",
        "*****+++++",
        "*****+++++"
    ],
    'medium': [
        "14 14 3 1",
        ". c <FILL>",
        "* c <BRDR>",
        "+ c None",
        "+++++++*******",
        "+++++++*******",
        "+++++++*******",
        "+++++++....***",
        "+++++++....***",
        "+++++++....***",
        "+++++++....***",
        "***....+++++++",
        "***....+++++++",
        "***....+++++++",
        "***....+++++++",
        "*******+++++++",
        "*******+++++++",
        "*******+++++++"
    ],
    'large': [
        "20 20 3 1",
        ". c <FILL>",
        "* c <BRDR>",
        "+ c None",
        "++++++++++**********",
        "++++++++++**********",
        "++++++++++**********",
        "++++++++++**********",
        "++++++++++......****",
        "++++++++++......****",
        "++++++++++......****",
        "++++++++++......****",
        "++++++++++......****",
        "++++++++++......****",
        "****......++++++++++",
        "****......++++++++++",
        "****......++++++++++",
        "****......++++++++++",
        "****......++++++++++",
        "****......++++++++++",
        "**********++++++++++",
        "**********++++++++++",
        "**********++++++++++",
        "**********++++++++++"
    ],
    'extra large': [
        "30 30 3 1",
        ". c <FILL>",
        "* c <BRDR>",
        "+ c None",
        "+++++++++++++++***************",
        "+++++++++++++++***************",
        "+++++++++++++++***************",
        "+++++++++++++++***************",
        "+++++++++++++++***************",
        "+++++++++++++++***************",
        "+++++++++++++++.........******",
        "+++++++++++++++.........******",
        "+++++++++++++++.........******",
        "+++++++++++++++.........******",
        "+++++++++++++++.........******",
        "+++++++++++++++.........******",
        "+++++++++++++++.........******",
        "+++++++++++++++.........******",
        "+++++++++++++++.........******",
        "******.........+++++++++++++++",
        "******.........+++++++++++++++",
        "******.........+++++++++++++++",
        "******.........+++++++++++++++",
        "******.........+++++++++++++++",
        "******.........+++++++++++++++",
        "******.........+++++++++++++++",
        "******.........+++++++++++++++",
        "******.........+++++++++++++++",
        "***************+++++++++++++++",
        "***************+++++++++++++++",
        "***************+++++++++++++++",
        "***************+++++++++++++++",
        "***************+++++++++++++++",
        "***************+++++++++++++++"
    ]
}

live = {
    'small': [
        "16 16 4 1",
        ". c <FILL>",
        "* c <BRDR>",
        "w c <FAMILY>",
        "x c None",
        "xxxxxxxxxxxxxxxx",
        "xxxxxxxxxxxxxxxx",
        "xxxxxxxxxxxxxxxx",
        "xxxxxxxxxxxxxxxx",
        "xxxxxxxxxxxxxxxx",
        "xxxxx***********",
        "xxxxx***********",
        "xxxxx**.......**",
        "xxxxx**.wwww..**",
        "xxxxx**.w.....**",
        "xxxxx**.www...**",
        "xxxxx**.w.....**",
        "xxxxx**.w.....**",
        "xxxxx**.......**",
        "xxxxx***********",
        "xxxxx***********"
    ],
    'medium': [
        "22 22 4 1",
        ". c <FILL>",
        "* c <BRDR>",
        "w c <FAMILY>",
        "x c None",
        "xxxxxxxxxxxxxxxxxxxxxx",
        "xxxxxxxxxxxxxxxxxxxxxx",
        "xxxxxxxxxxxxxxxxxxxxxx",
        "xxxxxxxxxxxxxxxxxxxxxx",
        "xxxxxxxxxxxxxxxxxxxxxx",
        "xxxxx*****************",
        "xxxxx*****************",
        "xxxxx*****************",
        "xxxxx***...........***",
        "xxxxx***..wwwwww...***",
        "xxxxx***..wwwwww...***",
        "xxxxx***..ww.......***",
        "xxxxx***..wwww.....***",
        "xxxxx***..wwww.....***",
        "xxxxx***..ww.......***",
        "xxxxx***..ww.......***",
        "xxxxx***..ww.......***",
        "xxxxx***...........***",
        "xxxxx***...........***",
        "xxxxx*****************",
        "xxxxx*****************",
        "xxxxx*****************"
    ],
    'large': [
        "27 27 4 1",
        ". c <FILL>",
        "* c <BRDR>",
        "w c <FAMILY>",
        "x c None",
        "xxxxxxxxxxxxxxxxxxxxxxxxxxx",
        "xxxxxxxxxxxxxxxxxxxxxxxxxxx",
        "xxxxxxxxxxxxxxxxxxxxxxxxxxx",
        "xxxxxxxxxxxxxxxxxxxxxxxxxxx",
        "xxxxxxxxxxxxxxxxxxxxxxxxxxx",
        "xxxxx**********************",
        "xxxxx**********************",
        "xxxxx**********************",
        "xxxxx**********************",
        "xxxxx****..............****",
        "xxxxx****..............****",
        "xxxxx****...wwwwwww....****",
        "xxxxx****...wwwwwww....****",
        "xxxxx****...ww.........****",
        "xxxxx****...ww.........****",
        "xxxxx****...wwwww......****",
        "xxxxx****...wwwww......****",
        "xxxxx****...ww.........****",
        "xxxxx****...ww.........****",
        "xxxxx****...ww.........****",
        "xxxxx****...ww.........****",
        "xxxxx****..............****",
        "xxxxx****..............****",
        "xxxxx**********************",
        "xxxxx**********************",
        "xxxxx**********************",
        "xxxxx**********************"
    ],
    'extra large': [
        "37 37 4 1",
        ". c <FILL>",
        "* c <BRDR>",
        "w c <FAMILY>",
        "x c None",
        "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        "xxxxx********************************",
        "xxxxx********************************",
        "xxxxx********************************",
        "xxxxx********************************",
        "xxxxx********************************",
        "xxxxx******....................******",
        "xxxxx******....................******",
        "xxxxx******....................******",
        "xxxxx******.....wwwwwwwww......******",
        "xxxxx******.....wwwwwwwww......******",
        "xxxxx******.....wwwwwwwww......******",
        "xxxxx******.....www............******",
        "xxxxx******.....www............******",
        "xxxxx******.....www............******",
        "xxxxx******.....wwwwwww........******",
        "xxxxx******.....wwwwwww........******",
        "xxxxx******.....wwwwwww........******",
        "xxxxx******.....www............******",
        "xxxxx******.....www............******",
        "xxxxx******.....www............******",
        "xxxxx******.....www............******",
        "xxxxx******.....www............******",
        "xxxxx******.....www............******",
        "xxxxx******....................******",
        "xxxxx******....................******",
        "xxxxx******....................******",
        "xxxxx******....................******",
        "xxxxx********************************",
        "xxxxx********************************",
        "xxxxx********************************",
        "xxxxx********************************",
        "xxxxx********************************"
    ]
}


def get_visdot(vis_colors):
    """Return a vis indicator pixbuf for vis_colors [border, fill]."""
    vdot = deepcopy(visdot)
    vdot[1] = vdot[1].replace('<BRDR>', vis_colors[0])
    vdot[2] = vdot[2].replace('<VISC>', vis_colors[1])
    return gtk.gdk.pixbuf_new_from_xpm_data(data=vdot)


def get_compdot(sdot, vdot):
    """Return a composite of state icon and vis indicator."""
    comp = sdot.copy()
    sdot.composite(comp, 0, 0, sdot.props.width, sdot.props.height,
                   0, 0, 1.0, 1.0, gtk.gdk.INTERP_HYPER, 255)
    vdot.composite(comp, 0, 0, vdot.props.width, vdot.props.height,
                   0, 0, 1.0, 1.0, gtk.gdk.INTERP_HYPER, 155)
    return comp


class DotMaker(object):
    """Make dot icons to represent task and family states."""

    FILTER_ICON_SIZES = ['small', 'medium']

    def __init__(self, theme, size='medium'):
        self.theme = theme
        self.size = size

        # Generate static state dots (only depend on theme).
        self.state_dots = {}
        self.state_dots['task'] = {}
        self.state_dots['family'] = {}
        for state in TASK_STATUSES_ORDERED:
            self.state_dots['task'][state] = self.get_icon(state)
            self.state_dots['family'][state] = self.get_icon(state,
                                                             is_family=True)
        self.empty = self.get_icon()

        self.icons = {}

    def get_icon(self, state=None, is_stopped=False, is_family=False,
                 is_filtered=False):
        """Generate a gtk.gdk.Pixbuf for a state.

        If is_stopped, generate a stopped form of the Pixbuf.
        If is_family, add a family indicator to the Pixbuf.
        """

        if state is None:
            xpm = empty[self.size]
        else:
            if state not in self.theme:
                # Use filled black. (This should not be possible, thanks to
                # inheritance from the default theme, but just in case).
                filled = True
                fill_color = "#000000"
                brdr_color = "#000000"
            else:
                color = self.theme[state]['color']
                if self.theme[state]['style'] == 'filled':
                    filled = True
                    fill_color = color
                    brdr_color = color
                else:
                    filled = False
                    fill_color = 'None'
                    brdr_color = color
            if is_stopped:
                xpm = deepcopy(stopped[self.size])
                xpm[1] = xpm[1].replace('<FILL>', fill_color)
                xpm[2] = xpm[2].replace('<BRDR>', brdr_color)
            elif is_filtered:
                if self.size in self.__class__.FILTER_ICON_SIZES:
                    size = self.size
                else:
                    size = self.__class__.FILTER_ICON_SIZES[-1]
                xpm = deepcopy(live[size])
                xpm[1] = xpm[1].replace('<FILL>', fill_color)
                xpm[2] = xpm[2].replace('<BRDR>', brdr_color)
            else:
                xpm = deepcopy(live[self.size])
                xpm[1] = xpm[1].replace('<FILL>', fill_color)
                xpm[2] = xpm[2].replace('<BRDR>', brdr_color)
            if is_family and '<FAMILY>' in xpm[3]:
                if filled:
                    xpm[3] = xpm[3].replace('<FAMILY>', 'None')
                else:
                    xpm[3] = xpm[3].replace('<FAMILY>', brdr_color)
            else:
                xpm[3] = xpm[3].replace('<FAMILY>', fill_color)

        return gtk.gdk.pixbuf_new_from_xpm_data(data=xpm)

    def get_image(self, state, is_stopped=False, is_filtered=False):
        """Returns a gtk.Image form of get_icon."""
        img = gtk.Image()
        img.set_from_pixbuf(
            self.get_icon(
                state, is_stopped=is_stopped, is_filtered=is_filtered))
        return img

    def _regen_task_icons_helper(self, states, dot_type, show_vis, gl_summary):
        """Helper for regenerate_task_icons()."""
        for id_, summary in states.items():
            name, _ = TaskID.split(id_)
            state = summary['state']
            icon = self.state_dots[dot_type][state]
            if show_vis:
                try:
                    vdot = get_visdot(gl_summary['vis_conf'][name])
                except KeyError:
                    # Back compat <= 6.10.2 (gcylc [visualisation] indicators)
                    pass
                else:
                    icon = get_compdot(icon, vdot)
            self.icons[id_] = icon

    def regenerate_task_icons(self, states, fam_states, show_vis, gl_sumry):
        """Generate dot icons for all tasks and families."""
        self.icons = {}
        self._regen_task_icons_helper(states, 'task', show_vis, gl_sumry)
        self._regen_task_icons_helper(fam_states, 'family', show_vis, gl_sumry)
