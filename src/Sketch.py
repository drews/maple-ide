"""Class for modelling a sketch, which is just a collection of files
we compile together as a project.

Sketch objects are meant to represent the _desired_ on-disk state of a
set of files.  However, if saves fail etc., a Sketch might get ahead
of the disk.

Sketches know how to compile themselves.  This mixes model/controller
a little bit, but in a way that I'm ok with."""

from __future__ import with_statement

import os.path
import re
import shutil
import subprocess
import tempfile
import zipfile
from os.path import join
from subprocess import PIPE, STDOUT

import preprocess as PP
import settings
from settings import SKETCH_EXN as EXN

#-----------------------------------------------------------------------------#

class MalformedSketchError(RuntimeError):

    def __init__(self, *args, **kwargs):
        RuntimeError.__init__(self, *args, **kwargs)

# FIXME decide if we want to support real files in sketch folders
SKETCH_EXTS = [EXN[1:], u'c', u'cpp', u'h']

#-----------------------------------------------------------------------------#

class Sketch(object):

    def __init__(self, user_interface, main_file, unsaved=False):
        """Create a Sketch object.

        main_file: absolute path to main sketch file in top level of
        the sketch's directory.

        user_interface: ui.UserInterface-alike object

        unsaved: set this to True if the sketch doesn't have any files
        on disk yet
        """
        if not main_file.endswith(EXN):
            raise ValueError(u'invalid main file extension: %s' % main_file)
        self.main_file = main_file
        self.main_basename = os.path.basename(main_file)
        self.dir = os.path.dirname(main_file)
        self.name = os.path.basename(self.dir)
        self.sources = self._reload_sources(unsaved) # {basename: Code}
        self.ui = user_interface
        self.build_dir = tempfile.mkdtemp(dir=settings.BUILD_DIR)
        self.compiling = False  # currently compiling?
        self.no_dir = unsaved

    def _strip_ext(self, sketch_file):
        return sketch_file[:-len(EXN)]

    def _ext(self, path):
        rsplit = path.rsplit(u'.')
        return rsplit[1] if len(rsplit) > 1 else None

    def redisplay_ui(self):
        self.ui.redisplay()

    def abs_path(self, basename):
        return join(self.dir, basename)

    def reset_directory(self, d, create=False):
        path = path.rstrip(os.path.sep) # NB '/' ==> '' haha oops

        if create and not os.path.isdir(path):
            try:
                os.makedirs(path)
            except:
                err = (u"Could not save to folder '%s', please choose " + \
                           u"another folder") % os.path.basename(path)
                self.ui.show_error(u"Save failed", err)
                return

        self.dir = d.rstrip(os.path.sep)
        self.name = os.path.basename(self.dir)

    def upload(self): # assumes build dir is all set up nice
        # FIXME gotta respect MCU, BOARD, etc.
        self.ui.clear_subprocess_window()
        make = settings.MAKE_PATH
        lmaple = settings.LIB_MAPLE_HOME
        child = subprocess.Popen([make, u'SRCROOT=%s' % lmaple, u'install'],
                                 stdout=PIPE, stderr=STDOUT,
                                 cwd=self.build_dir)
        out_err = child.stdout
        status = child.poll()
        while status is None:
            line = self.prettify_uploader_line(out_err.readline())
            self.ui.append_subprocess_output(line)
            status = child.poll()
        # FIXME maybe need to pull out the rest of the lines?
        self.ui.set_status(status, u'upload')

    def prettify_uploader_line(self, line): # TODO
        return line

    def cleanup(self):
        shutil.rmtree(self.build_dir)

    def stop_compiling(self, FIXME_ignore=False): # TODO
        if FIXME_ignore: return
        self.ui.show_error(u"Not implemented yet", u"Sorry!")

    def compile(self):
        """Assumes the sketch is synced with the hard disk."""
        self.ensure_existence() # ok, arduino, we'll check a little, too

        if self.compiling: self.stop_compiling(FIXME_ignore=True)

        # make isn't always so smart about what needs replacing, so do
        # the equivalent of 'make clean' by nuking the build directory.
        # (don't actually run make clean, because that would be slower)
        shutil.rmtree(self.build_dir)
        self.build_dir = tempfile.mkdtemp(dir=settings.BUILD_DIR)

        self.compiling=True

        try:
            # generate all the c++, compute offsets, and put it all into
            # the build directory
            self.preprocess()

            # set up the ui
            self.ui.clear_subprocess_window()

            # do the compilation, reporting errors, status updates, etc.
            # via the self.ui callback methods
            self.run_make()
        finally:
            self.compiling = False

    def preprocess(self):
        # split sketch files into c/c++ and pde files
        sketch_sources = {}
        cxx_sources = []
        for basename, code in self.sources.iteritems():
            if basename.endswith(EXN): sketch_sources[basename] = code
            else: cxx_sources.append(basename)

        # concatenate all of the pde sources, and compute their
        # initial offsets
        offset = 0
        sketch_lines = []
        for basename, code in sketch_sources.iteritems():
            src_lines = code.code.splitlines()
            nlines = len(src_lines)
            sketch_lines.extend(src_lines)
            code.offset = nlines
            offset += nlines

        # do the work
        preprocessed = PP.preprocess(sketch_lines)
        header = preprocessed[u'header']
        main = preprocessed[u'main']
        imports = preprocessed[u'imports']

        # update our offsets based on the number of header lines
        header_offset = len(header)
        for code in sketch_sources.itervalues():
            code.offset += header_offset

        # dump everything into the build directory
        # FIXME this breaks if they have a file named main.cpp already
        with open(join(self.build_dir, u'main.cpp'),'w') as main_cpp:
            main_cpp.write(u'\n'.join(header))
            main_cpp.write(u'\n'.join(sketch_lines))
            main_cpp.write(u'\n'.join(main))
        for import_ in imports:
            shutil.copy(join(settings.SKETCHBOOK_LIB_PATH, import_),
                        self.build_dir)
        for basename in cxx_sources:
            shutil.copy(join(self.dir, basename), self.build_dir)


    def run_make(self): # assumes self.build_dir is all set up
        make = settings.MAKE_PATH
        lmaple = settings.LIB_MAPLE_HOME
        if u'Makefile' not in os.listdir(lmaple):
            self.ui.show_error(u"Bad libmaple directory",
                               u"The libmaple directory on your system (%s)"% \
                                   lmaple + u' is missing a Makefile.  ' + \
                                   u'Cannot verify sketch.')
            return
        shutil.copy(join(lmaple,u'Makefile'), self.build_dir)
        # FIXME need to incorporate things like FLASH vs. RAM
        child = subprocess.Popen([make, u'SRCROOT=%s' % lmaple],
                                 stdout=PIPE, stderr=STDOUT,
                                 cwd=self.build_dir)
        out_err = child.stdout
        status = child.poll()
        # FIXME this will block, so we won't be able to halt
        # compilation until a multithreaded solution is figured out
        while status is None:
            line = self.prettify_compiler_line(out_err.readline())
            self.ui.append_subprocess_output(line)
            status = child.poll()
        # FIXME maybe need to pull out the rest of the lines (run a
        # final out_err.readlines() here) -- some seem to be missing
        # from the subprocess window; not sure
        self.ui.set_status(status, u'compilation')

    def prettify_compiler_line(self, line): # TODO
        return line

    def archive(self, archive_path=u''):
        #TODO: Unicode compliance?
        if archive_path == u"":
            archive_path= os.path.join(settings.SKETCHBOOK_PATH, self.dir) +".zip"
        zip = zipfile.ZipFile(archive_path, 'w', compression=zipfile.ZIP_DEFLATED)
        for root, dirs, files in os.walk(self.dir):
            archive_root = os.path.abspath(root)[len(os.path.abspath(self.dir)):]
            for f in files:
                fullpath = os.path.join(root, f)
                archive_name = os.path.join(archive_root, f)
                print f
                zip.write(fullpath, archive_name, zipfile.ZIP_DEFLATED)
        zip.close()

    def save(self, message_on_error=True):
        if self.no_dir:
            try:
                os.makedirs(self.dir)
                self.no_dir = False
            except:
                err = u'Could not create directory:\n\t%s\n' % self.dir
                err += u'Please save your sketch in another location.'
                self.ui.show_error(u'Save Failed', err)
                return False

        failed_saves = []
        for basename, code in self.sources.iteritems():
            path = join(self.dir, basename)
            try:
                with open(path, 'w') as f:
                    f.write(code.code)
            except Exception as e:
                print u"Couldn't save %s. Reason: %s" % (basename, str(e))
                failed_saves.append(basename)

        if failed_saves:
            if message_on_error:
                if len(failed_saves) == 1:
                    err = u'Could not save file ' + failed_saves[0] + '. ' + \
                        u'Please save your sketch in another location.'
                else:
                    err = u"The following files could not be saved: " + \
                        u', '.join(failed_saves) + \
                        u'.  Please save your sketch in another location.'
                self.ui.show_error(u"Save Failed", err)
            return False
        return True

    def _reload_sources(self, unsaved=False):
        # DOESN'T ACTUALLY MODIFY self.sources

        # Load the sketch files from disk, and pack them into a dict
        # suitable for saving into self.sources.  If `unsaved' is
        # true, assumes the sketch is new and hasn't got any files;
        # just makes empty Code objects.
        self.num_files = 0

        if unsaved:
            return {self.main_basename : Code(u'')}

        sources = {}
        main_found = False
        for f in os.listdir(self.dir):
            abs_f = self.abs_path(f)
            if f.startswith(u'.') or self._ext(f) not in SKETCH_EXTS or \
                    not os.path.isfile(abs_f):
                continue

            if abs_f == self.main_file: main_found = True
            with open(abs_f, 'r') as f_in:
                source = f_in.read()
                sources[os.path.basename(f)] = Code(source)

        if not main_found:
            # TODO better error reporting
            raise MalformedSketchError(u'missing main file %s from dir %d' % \
                                           (self.main_file, self.dir))

        return sources

    def source(self, basename):
        return self.sources[basename].code

    def replace_source(self, basename, new_code):
        if basename not in self.sources:
            # TODO better error reporting
            raise ValueError(u'%s not a source' % basename)
        self.sources[basename].code = new_code

    def insert_source(self, basename, new_code):
        if basename in self.sources:
            # TODO better error reporting
            raise ValueError(u'%s already a source' % basename)
        self.sources[basename].code = new_code

    def __get_num_sources(self):
        return len(self.sources)
    num_sources = property(fget=__get_num_sources)

    def ensure_existence(self):
        if os.path.exists(self.dir): return True
        self.ui.show_ok_warning([u"Sketch disappeared",
                                 u"Your sketch folder has disappeared.\n" + \
                                     u"Maple IDE will attempt to restore " + \
                                     u"your source code, but other data " + \
                                     u"will be lost."])
        self.no_dir = True
        if not self.save():
            self.ui.show_ok_warning([u"Sketch restoration failed",
                                     u"Could not restore all of your " + \
                                         u"source code.  Some changes " + \
                                         u"may be lost.  You should attempt "+\
                                         u"to save your work elsewhere."])

    def __str__(self):
        codes_str = [u'// ----------- FILE: %s ----------\n%s' % \
                         (basename, str(code)) \
                     for basename, code in self.sources.iteritems()]
        return u'Sketch: %s\n\n%s' % (self.main_basename,
                                      u'\n'.join(codes_str))

#-----------------------------------------------------------------------------#

class Code(object):
    """Source for a sketch file and associated data."""
    # ok, so there's no associated data yet, but there will be once
    # preprocessing works
    def __init__(self, code):
        self.code = code

    def __str__(self):
        return self.code

    def __repr__(self):
        return u'Code("%s")' % self.code
