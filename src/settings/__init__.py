"""Global settings file.
"""

import os.path
import tempfile

# FIXME this is just stubbed out real quick; do it for real

#--------------- System settings: YOU MUST EDIT THESE (for now) --------------#

# path to the make executable on your system.  this should be fine for
# almost any UNIX out there.  it works on OS X.
#
# eventually, we'll have to figure out how to bundle make as an
# included dependency for all three platforms.  if you do this for me,
# you are my hero.  especially on windows.  if that sounds like
# something you want to do, here is a place to start:
#
# http://gnuwin32.sourceforge.net/packages/make.htm
#
# especially these prebuilt binaries + dependencies:
# http://gnuwin32.sourceforge.net/downlinks/make-bin-zip.php
# http://gnuwin32.sourceforge.net/downlinks/make-dep-zip.php
MAKE_PATH = u'/usr/bin/make'

# place where your sketches live.  this should be OK on os x, if you
# accepted the default settings on the current MapleIDE
SKETCHBOOK_PATH = os.path.expanduser(u'~/Documents/MapleIDE')

# place where your additional libraries live.  this should also be OK
# on os x if you accepted the default
SKETCHBOOK_LIB_PATH = os.path.expanduser(u'~/Documents/MapleIDE/libraries')

# Directory containing libmaple and wirish.
# TODO preference to allow environment variable override
LIB_MAPLE_HOME = u'/Users/mbolivar/hack/leaf/libmaple'

#----------------------------- App-local settings ----------------------------#

# You shouldn't have to edit these (i.e., consider it a bug and let
# Marti know if you find that you must)

# The extension we use for our sketches.  DO NOT SAY .pde ANYWHERE!
# use this instead.  it might not be a bad idea to change our file
# extension.  not sure yet.
SKETCH_EXN = u'.pde'

# Build directory parent: all of the sketch-level build directories
# are contained in this top-level one.  Just to be safe, the app nukes
# this directory within a finally: upon exit from the main loop
BUILD_DIR = tempfile.mkdtemp(prefix=u'maple-build')

# Resources (GUI images, reference docs, etc.)
TOOLBAR_BUTTONS = u'buttons.png'
RESOURCE_DIR = os.path.abspath(u'../resources')
REFERENCE_DIR = os.path.join(RESOURCE_DIR, 'reference')
EXAMPLEBOOK_DIR = os.path.join(RESOURCE_DIR, 'examples')
