#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2014 Hilary Oliver, NIWA
#C:
#C: This program is free software: you can redistribute it and/or modify
#C: it under the terms of the GNU General Public License as published by
#C: the Free Software Foundation, either version 3 of the License, or
#C: (at your option) any later version.
#C:
#C: This program is distributed in the hope that it will be useful,
#C: but WITHOUT ANY WARRANTY; without even the implied warranty of
#C: MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#C: GNU General Public License for more details.
#C:
#C: You should have received a copy of the GNU General Public License
#C: along with this program.  If not, see <http://www.gnu.org/licenses/>.

import gtk
from copy import deepcopy
from cylc.cfgspec.gcylc import gcfg
from cylc.task_state import task_state

stopped = {
        'small' : [
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
                "*****+++++" ],
        'medium' : [
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
                "*******+++++++"], 

        'large' : [
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
                "**********++++++++++" ]
        }


live = {
        'small' : [
                "11 11 5 1",
                ".	c <FILL>",
                "*	c <BRDR>",
                "+  c None",
                "b  c <FAM_BLACK>",
                "w  c <FAM_WHITE>",
                "***********",
                "***********",
                "**wwwww..**",
                "**wbbbw..**",
                "**wbbbw..**",
                "**wbbbw..**",
                "**wwwww..**",
                "**.......**",
                "**.......**",
                "***********",
                "***********" ],
        'medium' : [
                "17 17 5 1",
                ".	c <FILL>",
                "*	c <BRDR>",
                "+  c None",
                "b  c <FAM_BLACK>",
                "w  c <FAM_WHITE>",
                "*****************",
                "*****************",
                "*****************",
                "***wwwwwww....***",
                "***wbbbbbw....***",
                "***wbbbbbw....***",
                "***wbbbbbw....***",
                "***wbbbbbw....***",
                "***wbbbbbw....***",
                "***wwwwwww....***",
                "***...........***",
                "***...........***",
                "***...........***",
                "***...........***",
                "*****************",
                "*****************",
                "*****************"], 

        'large' : [
                "22 22 5 1",
                ".	c <FILL>",
                "*	c <BRDR>",
                "+  c None",
                "b  c <FAM_BLACK>",
                "w  c <FAM_WHITE>",
                "**********************",
                "**********************",
                "**********************",
                "**********************",
                "****wwwwwwww......****",
                "****wbbbbbbw......****",
                "****wbbbbbbw......****",
                "****wbbbbbbw......****",
                "****wbbbbbbw......****",
                "****wbbbbbbw......****",
                "****wwwwwwww......****",
                "****..............****",
                "****..............****",
                "****..............****",
                "****..............****",
                "****..............****",
                "****..............****",
                "****..............****",
                "**********************",
                "**********************", 
                "**********************",
                "**********************"]
        }


class DotMaker(object):

    """Make dot icons to represent task and family states."""

    def __init__(self, theme, size=None):
        self.theme = theme
        self.size = size or gcfg.get(['dot icon size'])

    def get_icon(self, state=None, is_stopped=False, is_family=False):
        """Generate a gtk.gdk.Pixbuf for a state.

        If is_stopped, generate a stopped form of the Pixbuf.
        If is_family, add a family indicator to the Pixbuf.
        """
        if is_stopped:
            xpm = deepcopy(stopped[self.size])
        else:
            xpm = deepcopy(live[self.size])

        if not state or state not in self.theme:
            # empty icon ('None' is xpm transparent)
            cols = ['None', 'None']
        else:
            style = self.theme[state]['style']
            color = self.theme[state]['color']
            if style == 'filled':
                cols = [color, color]
            else:
                # unfilled with border
                cols = ['None', color]

        xpm[1] = xpm[1].replace('<FILL>', cols[0])
        xpm[2] = xpm[2].replace('<BRDR>', cols[1])
        if is_family:
            xpm[4] = xpm[4].replace('<FAM_BLACK>', cols[1])
            xpm[5] = xpm[5].replace('<FAM_WHITE>', 'None')
        else:
            xpm[4] = xpm[4].replace('<FAM_BLACK>', cols[0])
            xpm[5] = xpm[5].replace('<FAM_WHITE>', cols[0])

        # NOTE: to get a pixbuf from an xpm file, use:
        #    gtk.gdk.pixbuf_new_from_file('/path/to/file.xpm')
        return gtk.gdk.pixbuf_new_from_xpm_data(data=xpm)

    def get_image(self, state, is_stopped=False):
        """Returns a gtk.Image form of get_icon."""
        img = gtk.Image()
        img.set_from_pixbuf(self.get_icon(state, is_stopped=is_stopped))
        return img

    def get_dots(self):
        dots = {'task' : {}, 'family' : {}}
        for state in task_state.legal:
            dots['task'][state] = self.get_icon(state)
            dots['family'][state] = self.get_icon(state, is_family=True)
        empty_dot = self.get_icon()
        dots['task']['empty'] = empty_dot
        dots['family']['empty'] = empty_dot
        return dots
