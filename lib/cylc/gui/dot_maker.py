#!/usr/bin/env python

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2015 NIWA
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
from cylc.task_state import task_state


empty = {}
empty['small'] = ["11 11 1 1", ". c None"]
empty['small'].extend(["..........."]*11)
empty['medium'] = ["17 17 1 1", ". c None"]
empty['medium'].extend(["................."]*17)
empty['large'] = ["22 22 1 1", ". c None"]
empty['large'].extend(["......................"]*22)
empty['extra large'] = ["32 32 1 1", ". c None"]
empty['extra large'].extend(["................................"]*32)

stopped = {
    'small': [
        "10 10 3 1",
        ".	c <FILL>",
        "*	c <BRDR>",
        "+  c None",
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
        ".	c <FILL>",
        "*	c <BRDR>",
        "+  c None",
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
        ".	c <FILL>",
        "*	c <BRDR>",
        "+  c None",
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
        ".	c <FILL>",
        "*	c <BRDR>",
        "+  c None",
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
        "11 11 3 1",
        ".	c <FILL>",
        "*	c <BRDR>",
        "w  c <FAMILY>",
        "***********",
        "***********",
        "**.......**",
        "**.wwww..**",
        "**.w.....**",
        "**.www...**",
        "**.w.....**",
        "**.w.....**",
        "**.......**",
        "***********",
        "***********"
    ],
    'medium': [
        "17 17 3 1",
        ".	c <FILL>",
        "*	c <BRDR>",
        "w  c <FAMILY>",
        "*****************",
        "*****************",
        "*****************",
        "***...........***",
        "***..wwwwww...***",
        "***..wwwwww...***",
        "***..ww.......***",
        "***..wwww.....***",
        "***..wwww.....***",
        "***..ww.......***",
        "***..ww.......***",
        "***..ww.......***",
        "***...........***",
        "***...........***",
        "*****************",
        "*****************",
        "*****************"
    ],
    'large': [
        "22 22 3 1",
        ".	c <FILL>",
        "*	c <BRDR>",
        "w  c <FAMILY>",
        "**********************",
        "**********************",
        "**********************",
        "**********************",
        "****..............****",
        "****..............****",
        "****...wwwwwww....****",
        "****...wwwwwww....****",
        "****...ww.........****",
        "****...ww.........****",
        "****...wwwww......****",
        "****...wwwww......****",
        "****...ww.........****",
        "****...ww.........****",
        "****...ww.........****",
        "****...ww.........****",
        "****..............****",
        "****..............****",
        "**********************",
        "**********************",
        "**********************",
        "**********************"
    ],
    'extra large': [
        "32 32 3 1",
        ".	c <FILL>",
        "*	c <BRDR>",
        "w  c <FAMILY>",
        "********************************",
        "********************************",
        "********************************",
        "********************************",
        "********************************",
        "******....................******",
        "******....................******",
        "******....................******",
        "******.....wwwwwwwww......******",
        "******.....wwwwwwwww......******",
        "******.....wwwwwwwww......******",
        "******.....www............******",
        "******.....www............******",
        "******.....www............******",
        "******.....wwwwwww........******",
        "******.....wwwwwww........******",
        "******.....wwwwwww........******",
        "******.....www............******",
        "******.....www............******",
        "******.....www............******",
        "******.....www............******",
        "******.....www............******",
        "******.....www............******",
        "******....................******",
        "******....................******",
        "******....................******",
        "******....................******",
        "********************************",
        "********************************",
        "********************************",
        "********************************",
        "********************************"
    ]
}


class DotMaker(object):
    """Make dot icons to represent task and family states."""

    FILTER_ICON_SIZES = ['small', 'medium']

    def __init__(self, theme, size='medium'):
        self.theme = theme
        self.size = size

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

    def get_dots(self):
        dots = {'task': {}, 'family': {}}
        for state in task_state.legal:
            dots['task'][state] = self.get_icon(state)
            dots['family'][state] = self.get_icon(state, is_family=True)
        dots['task']['empty'] = self.get_icon()
        dots['family']['empty'] = self.get_icon()
        return dots
