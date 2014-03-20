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
                "10 10 3 1",
                ".	c <FILL>",
                "*	c <BRDR>",
                "+  c None",
                "**********",
                "**********",
                "**......**",
                "**......**",
                "**......**",
                "**......**",
                "**......**",
                "**......**",
                "**********",
                "**********" ],
        'medium' : [
                "14 14 3 1",
                ".	c <FILL>",
                "*	c <BRDR>",
                "+  c None",
                "**************",
                "**************",
                "**************",
                "***........***",
                "***........***",
                "***........***",
                "***........***",
                "***........***",
                "***........***",
                "***........***",
                "***........***",
                "**************",
                "**************",
                "**************"], 

        'large' : [
                "20 20 3 1",
                ".	c <FILL>",
                "*	c <BRDR>",
                "+  c None",
                "********************",
                "********************",
                "********************",
                "********************",
                "****............****",
                "****............****",
                "****............****",
                "****............****",
                "****............****",
                "****............****",
                "****............****",
                "****............****",
                "****............****",
                "****............****",
                "****............****",
                "****............****",
                "********************",
                "********************", 
                "********************",
                "********************"]
        }


class DotMaker(object):

    """Make a dot icon for a task state."""

    def __init__( self, theme ):
        self.theme = theme

    def get_icon( self, state=None, is_stopped=False ):
        """Generate a gtk.gdk.Pixbuf for a state.

        if is_stopped, generate a stopped form of the Pixbuf.

        """
        size = gcfg.get(['dot icon size'])
        if is_stopped:
            xpm = deepcopy(stopped[size])
        else:
            xpm = deepcopy(live[size])

        if not state or state not in self.theme:
            # empty icon ('None' is xpm transparent)
            cols = ['None', 'None' ]
        else:
            style = self.theme[state]['style']
            color = self.theme[state]['color']
            if style == 'filled':
                cols = [ color, color ]
            else:
                # unfilled with thick border
                cols = [ 'None', color ]

        xpm[1] = xpm[1].replace( '<FILL>', cols[0] )
        xpm[2] = xpm[2].replace( '<BRDR>', cols[1] )

        # NOTE: to get a pixbuf from an xpm file, use:
        #    gtk.gdk.pixbuf_new_from_file('/path/to/file.xpm')
        return gtk.gdk.pixbuf_new_from_xpm_data( data=xpm )

    def get_image( self, state, is_stopped=False ):
        """Returns a gtk.Image form of get_icon."""
        img = gtk.Image()
        img.set_from_pixbuf( self.get_icon( state, is_stopped=is_stopped ) )
        return img

