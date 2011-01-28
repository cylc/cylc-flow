import gtk
import pygtk
####pygtk.require('2.0')

class warning_dialog(object):
    def __init__( self, msg ):
        self.dialog = gtk.MessageDialog( None,
                gtk.DIALOG_DESTROY_WITH_PARENT, gtk.MESSAGE_WARNING,
                gtk.BUTTONS_CLOSE, msg )

    def warn( self ):
        self.dialog.run()
        self.dialog.destroy()

class info_dialog(object):
    def __init__( self, msg ):
        self.dialog = gtk.MessageDialog( None,
                gtk.DIALOG_DESTROY_WITH_PARENT, gtk.MESSAGE_INFO,
                gtk.BUTTONS_CLOSE, msg )

    def inform( self ):
        self.dialog.run()
        self.dialog.destroy()
