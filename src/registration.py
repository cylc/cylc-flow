#!/usr/bin/env python

import pickle
import os, sys, re

# local and central suite registration

class RegistrationError( Exception ):
    """
    Attributes:
        message - what the problem is. 
    """
    def __init__( self, msg ):
        self.msg = msg
    def __str__( self ):
        return repr(self.msg)

class RegistrationTakenError( RegistrationError ):
    def __init__( self, suite, owner=None ):
        self.msg = "ERROR: Another suite is registered as " + suite
        if owner:
            self.msg += ' (' + owner + ')'

class SuiteNotRegisteredError( RegistrationError ):
    def __init__( self, suite ):
        self.msg = "ERROR: Suite not found " + suite

class groupNotFoundError( RegistrationError ):
    def __init__( self, group, owner=None ):
        self.msg = "ERROR: group not found " + group
        if owner:
            self.msg += ' (' + owner + ')'

class RegistrationNotValidError( RegistrationError ):
    pass

def qualify( suite, withowner=False ):
    # restore the group name to suites in the 'default' group.
    if re.match( '^(\w+):(\w+):(\w+)$', suite ):
        # owner:group:name
        pass
    elif re.match( '^(\w+):(\w+)$', suite ):
        # group:name
        if withowner:
            suite = os.environ['USER'] + ':' + suite
    elif re.match( '^(\w+)$', suite ): 
        # default group
        suite = 'default:' + suite
        if withowner:
            suite = os.environ['USER'] + ':' + suite
    else:
        raise RegistrationError, 'Illegal suite name: ' + suite
    return suite

def unqualify( suite ):
    # strip the owner from all suites,
    # and the group from suites in the 'default' group.
    m = re.match( '^(\w+):(\w+):(\w+)$', suite )
    if m:
        owner, group, name = m.groups()
        suite = group + ':' + name
    m = re.match( '^(\w+):(\w+)$', suite )
    if m:
        group, name = m.groups()
        if group == 'default':
            suite = name
    elif re.match( '^(\w+)$', suite ): 
        pass
    else:
        raise RegistrationError, 'Illegal suite name: ' + suite
    return suite

class regsplit( object ):
    def __init__( self, suite ):
        user = os.environ['USER']
        # suite can be:
        # 1/ owner:group:name
        # 2/ group:name (owner is $USER)
        # 3/ name (owner is $USER, group is 'default')
        m = re.match( '^(\w+):(\w+):(\w+)$', suite )
        if m:
            owner, group, name = m.groups()
        else:
            m = re.match( '^(\w+):(\w+)$', suite )
            if m:
                group, name = m.groups()
                owner = user
            else:
                if re.match( '^\w+$', suite ):
                    group = 'default'
                    name = suite
                    owner = user
                else:
                    raise RegistrationError, 'Illegal suite name: ' + suite
        self.owner = owner
        self.group = group
        self.name = name

    def get( self ):
        return self.owner, self.group, self.name
    def get_full( self ):
        return self.owner + ':' + self.group + ':' + self.name
    def get_partial( self ):
        return self.group + ':' + self.name
    def get_name( self ):
        return self.name

class regdb(object):
    """
    A simple suite registration database.
    Derived classes must provide:
     1/ __init__:
       + the database file path
       + and initial call to load_from_file().
    And:
     2/ suiteid():
       + to munge the fully qualified suite name (owner:group:name)
    """
    def load_from_file( self ):
        if not os.path.exists( self.file ):
            # this implies no suites have been registered
            return
        input = open( self.file, 'rb' )
        self.items = pickle.load( input )
        input.close()

    def dump_to_file( self ):
        output = open( self.file, 'w' )
        pickle.dump( self.items, output )
        output.close()

    def register( self, suite, dir, description='(no description supplied)' ):
        owner, group, name = regsplit( suite ).get()
        if owner != self.user:
            raise RegistrationError, 'You cannot register as another user'
        try:
            regdir, descr = self.items[owner][group][name]
        except KeyError:
            # not registered  yet, do it below.
            pass
        else:
            if regdir == dir:
                # OK, this suite is already registered
                self.print_reg( suite, prefix='(ALREADY REGISTERED)' )
                return
            else:
                # ERROR, another suite is already using this registration
                raise RegistrationTakenError( suite )

        # register the suite
        if owner not in self.items:
            self.items[owner] = {}
        if group not in self.items[owner]:
            self.items[owner][group] = {}
        self.items[owner][group][name] = (dir, description)

        self.print_reg( suite, prefix='REGISTERING' )

    def unregister( self, suite, verbose=False ):
        owner, group, name = regsplit(suite).get()
        if owner != self.user:
            #raise RegistrationError, 'You cannot unregister as another user'
            self.print_reg( suite )
            print "(can't unregister, wrong suite owner)"
            return
        self.print_reg(suite, prefix='DELETING', verbose=verbose )
        # delete it
        del self.items[owner][group][name]
        # delete the group if it is empty
        if len( self.items[owner][group].keys() ) == 0:
            del self.items[owner][group]
        # delete the user slot if it is empty
        if len( self.items[owner].keys() ) == 0:
            del self.items[owner]
    
    def unregister_all_fast( self ):
        print 'DELETING ALL REGISTRATIONS!'
        self.items = {}
 
    def unregister_group_fast( self, group ):
        print 'DELETING registration group ', group
        owner = self.user
        try:
            del self.items[owner][group]
        except KeyError:
            raise groupNotFoundError( group, owner ) 

    def unregister_all( self, verbose=False ):
        my_suites = self.get_list( ownerfilt=self.user )
        for suite, dir, descr in my_suites:
            self.unregister( suite, verbose=verbose )

    def unregister_multi( self, ownerfilt=None, groupfilt=None,
            namefilt=None, verbose=False, invalid=False ):
        changed = False
        owners = self.items.keys()
        owners.sort()
        owner_done = {}
        group_done = {}
        for owner in owners:
            owner_done[owner] = False
            if ownerfilt:
                if not re.match( ownerfilt, owner):
                    continue
            groups = self.items[owner].keys()
            groups.sort()
            for group in groups:
                group_done[group] = False
                if groupfilt:
                    if not re.match( groupfilt, group):
                        continue
                names = self.items[owner][group].keys()
                names.sort()
                for name in names:
                    if namefilt:
                        if not re.match( namefilt, name):
                            continue
                    if verbose:
                        if not owner_done[owner]:
                            print 'OWNER', owner + ':'
                            owner_done[owner] = True
                        if not group_done[group]:
                            print '  GROUP', group + ':'
                            group_done[group] = True
                    suite = owner + ':' + group + ':' + name
                    if invalid:
                        # unregister only if not valid
                        try:
                            self.check_valid( suite )
                        except RegistrationNotValidError, x:
                            print x
                        else:
                            continue
                    self.unregister( suite, verbose )
                    changed = True
        return changed

    def get( self, suite, owner=None ):
        # return suite definition directory
        owner, group, name = regsplit( suite ).get()
        try:
            dir, descr = self.items[owner][group][name]
        except KeyError:
            raise SuiteNotRegisteredError( suite )
        else:
            return ( dir, descr )

    def get_list( self, ownerfilt=None, groupfilt=None, namefilt=None ):
        # return filtered list of tuples:
        # [( suite, dir, descr ), ...]
        regs = []
        owners = self.items.keys()
        owners.sort()
        #print ownerfilt
        #print groupfilt
        #print namefilt
        for owner in owners:
            if ownerfilt:
                if not re.match( ownerfilt, owner ):
                    continue
            groups = self.items[owner].keys()
            groups.sort()
            for group in groups:
                if groupfilt:
                    if not re.match( groupfilt, group ):
                        continue
                names = self.items[owner][group].keys()
                names.sort()
                for name in names:
                    if namefilt:
                        if not re.match( namefilt, name ):
                            continue
                    dir,descr = self.items[owner][group][name]
                    regs.append( (self.suiteid(owner,group,name), dir, descr) )
        return regs

    def clean_all( self ):
        # delete ANY invalid registrations owned by anyone
        return self.unregister_multi( invalid=True )

    def check_valid( self, suite ):
        owner, group, name = regsplit( suite ).get()
        # raise an exception if the registration is not valid
        dir,descr = self.get( suite )
        if not os.path.isdir( dir ):
            raise RegistrationNotValidError, 'Directory not found: ' + dir
        file = os.path.join( dir, 'suite.rc' )
        if not os.path.isfile( file ): 
            raise RegistrationNotValidError, 'File not found: ' + file
        # OK

    def print_reg( self, suite, prefix='', verbose=False ):
        # check the registration exists:
        suite = regsplit( suite ).get_full()
        owner, group, name = regsplit( suite ).get()
        dir,descr = self.get( suite )
        if not verbose:
            print prefix, self.suiteid( owner,group,name ) + '    |' + descr + '|    ' + dir 
        else:
            print prefix, '     NAME ' + name + '    |' + descr + '|    ' + dir 

    def print_multi( self, ownerfilt=None, groupfilt=None, namefilt=None, verbose=False ):
        owners = self.items.keys()
        owners.sort()
        owner_done = {}
        group_done = {}
        count = 0
        for owner in owners:
            owner_done[owner] = False
            if ownerfilt:
                if not re.match( ownerfilt, owner):
                    continue
            groups = self.items[owner].keys()
            groups.sort()
            for group in groups:
                group_done[group] = False
                if groupfilt:
                    if not re.match( groupfilt, group):
                        continue
                names = self.items[owner][group].keys()
                names.sort()
                for name in names:
                    if namefilt:
                        if not re.match( namefilt, name):
                            continue
                    suite = owner + ':' + group + ':' + name
                    if verbose:
                        if not owner_done[owner]:
                            print 'OWNER', owner + ':'
                            owner_done[owner] = True
                        if not group_done[group]:
                            print '  GROUP', group + ':'
                            group_done[group] = True
                    self.print_reg( suite, verbose=verbose )
                    count += 1
        return count

class localdb( regdb ):
    """
    Local (user-specific) suite registration database.
    Internally, registration uses 'owner:group:name' 
    as for the central suite database, but for local
    single-user use, owner and default group are stripped off.
    """
    def __init__( self, file=None ):
        self.user = os.environ['USER']
        if file:
            # use for testing
            self.file = file
            dir = os.path.dirname( file )
        else:
            # file in which to store suite registrations
            dir = os.path.join( os.environ['HOME'], '.cylc' )
            self.file = os.path.join( dir, 'registrations' )

        # create initial database directory if necessary
        if not os.path.exists( dir ):
            try:
                os.makedirs( dir )
            except Exception,x:
                print "ERROR: failed to create directory:", dir
                print x
                sys.exit(1)

        self.items = {}  # items[owner][group][name] = (dir,description)
        self.load_from_file()

    def suiteid( self, owner, group, name ):
        # for local use, the user does not need the suite owner prefix
        if group == 'default':
            return name
        else:
            return group + ':' + name

    def print_multi( self, ownerfilt=None, groupfilt=None, namefilt=None, verbose=False ):
        # for local use, don't need to print the owner name
        owners = self.items.keys()
        group_done = {}
        count = 0
        if len(owners) == 0:
            # nothing registered
            return
        if len(owners) > 1:
            # THIS SHOULD NOT HAPPEN
            raise RegistrationError, 'ERROR: multiple owners in local registration db!'
        if owners[0] != self.user:
            # THIS SHOULD NOT HAPPEN
            raise RegistrationError, 'ERROR: wrong suite owner in local registration db!'
        owner = self.user
        # ignoring ownerfilt ... does this matter?
        groups = self.items[owner].keys()
        groups.sort()
        for group in groups:
            group_done[group] = False
            if groupfilt:
                if not re.match( groupfilt, group ):
                    continue
            names = self.items[owner][group].keys()
            names.sort()
            for name in names:
                if namefilt:
                    if not re.match( namefilt, name):
                        continue
                suite = owner + ':' + group + ':' + name
                if verbose:
                    if not group_done[group]:
                        print '  GROUP', group + ':'
                        group_done[group] = True
                self.print_reg( suite, verbose=verbose )
                count += 1
        return count

class centraldb( regdb ):
    """
    Central registration database for sharing suites between users.
    """
    def __init__( self, file=None ):
        self.user = os.environ['USER']
        if file:
            # use for testing
            self.file = file
            dir = os.path.dirname( file )
        else:
            # file in which to store suite registrations
            dir = os.path.join( os.environ['CYLC_DIR'], 'cdb' )
            self.file = os.path.join( dir, 'registrations' )

        # create initial database directory if necessary
        if not os.path.exists( dir ):
            try:
                os.makedirs( dir )
            except Exception,x:
                print "ERROR: failed to create directory:", dir
                print x
                sys.exit(1)

        self.items = {}  # items[owner][group][name] = (dir,description)
        self.load_from_file()

    def suiteid( self, owner, group, name ):
        return owner + ':' + group + ':' + name

if __name__ == '__main__':
    # unit test
    reg = localdb( os.path.join( os.environ['CYLC_DIR'], 'REGISTRATIONS'))
    reg.unregister_multi()
    try:
        reg.register( 'foo', 'suites/userguide',      'the quick'    ) # new
        reg.register( 'ONE:bar', 'suites/userguide',  'brown fox'    ) # new
        reg.register( 'TWO:bar', 'suites/userguidex', 'jumped over'  ) # new
        reg.register( 'TWO:baz', 'suites/userguidex' ) # new
        reg.register( 'TWO:baz', 'suites/userguidex' ) # OK repeat
        reg.register( 'TWO:baz', 'suites/userguidexx') # BAD repeat
    except RegistrationError,x:
        print x
    reg.dump_to_file()

    reg2 = localdb( os.path.join( os.environ['CYLC_DIR'], 'REGISTRATIONS'))
    reg2.load_from_file()
    reg2.print_multi()
