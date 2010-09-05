"""Class for modelling a sketch, which is just a collection of files
we compile together as a project."""

from __future__ import with_statement

import os.path

#-----------------------------------------------------------------------------#

class MalformedSketchError(RuntimeError):

    def __init__(self, *args, **kwargs):
        RuntimeError.__init__(self, *args, **kwargs)

SKETCH_EXTS = ['pde', 'c', 'cpp', 'h']

#-----------------------------------------------------------------------------#

def make_new_sketch():
    sk = Sketch(None)

class Sketch(object):

    def __init__(self, user_interface, main_file=None):
        """Create a Sketch object.

        main_file = absolute path to main sketch file in top level of
        the sketch's directory.

        user_interface = ui.UserInterface-alike object
        """
        if not main_file.endswith('.pde'):
            raise ValueError('invalid main file extension: %s' % main_file)
        self.main_file = main_file
        self.main_name = os.path.basename(main_file)
        self.sketch_dir = os.path.dirname(main_file)
        self.sketch_name = os.path.basename(self.sketch_dir)
        self.sources = self.reload_sources() # {basename: code}
        self.ui = user_interface
        self.saved = False

    def _strip_ext(self, pde_file):
        return pde_file[:-4]

    def _ext(self, path):
        rsplit = path.rsplit('.')
        return rsplit[1] if len(rsplit) > 1 else None

    def redisplay_ui(self):
        self.ui.redisplay()

    def abs_path(self, basename):
        return os.path.join(self.sketch_dir, basename)

    def save(self):
        sketchbook.save(this)

    def reload_sources(self):
        self.num_files = 0

        sources = {}
        main_found = False
        for f in os.listdir(self.sketch_dir):
            abs_f = self.abs_path(f)
            if f.startswith('.') or self._ext(f) not in SKETCH_EXTS or \
                    not os.path.isfile(abs_f):
                continue

            if abs_f == self.main_file: main_found = True
            with open(abs_f, 'r') as f_in:
                source = f_in.read()
                sources[f] = source

        if not main_found:
            # TODO better error reporting
            raise MalformedSketchError('missing main file %s from dir %d' % \
                                           (self.main_file, self.sketch_dir))

        return sources

    def source(self, basename):
        return self.sources[basename]

    def replace_source(self, basename, new_code):
        if basename not in self.sources:
            # TODO better error reporting
            raise ValueError('%s not a source' % basename)
        self.sources[basename] = new_code

    def insert_source(self, basename, new_code):
        if basename in self.sources:
            # TODO better error reporting
            raise ValueError('%s already a source' % basename)
        self.sources[basename] = new_code

    def __get_num_sources(self):
        return len(self.sources)
    num_sources = property(fget=__get_num_sources)

    def ensure_existence(self):
        if os.path.exists(self.sketch_dir): return True
        self.ui.show_ok_warning(["Sketch disappeared",
                                 "Your sketch folder has disappeared.\n" + \
                                     "Maple IDE will attempt to restore " + \
                                     "your source code, but other data " + \
                                     "will be lost."])
        try:
            os.mkdirs(self.sketch_dir)
            for basename in self.sources:
                with open(self.abs_path(basename), 'w') as f_out:
                    f_out.write(self.sources[basename])
        except:
            self.ui.show_ok_warning(["Sketch restoration failed",
                                     "Could not restore all of your " + \
                                         "source code.  Some changes " + \
                                         "may be lost.  You should attempt " +\
                                         "to save your work elsewhere."])
        finally:
            self.redisplay_ui()


#-----------------------------------------------------------------------------#
