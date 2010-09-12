"""SketchFrame is our view class for a Sketch and the assorted operations
you can perform on it.  It's the usual Arduino-style editing window with
toolbar, tabbed notebook of all the files in the sketch, and compilation
output area.
"""

import os
import shutil
import sys
import webbrowser
import datetime
from pprint import pprint

import wx
import wx.aui
import wx.stc
from wx.aui import AuiNotebook

import resources
import settings
import examplebook as EB
import sketchbook as SB
from settings import SKETCH_EXN as EXN
from ui import UserInterface
from wx_util import *
from CPPStyledTextCtrl import CPPStyledTextCtrl
from Sketch import Sketch

STATUS_SUCCESS = 0              # FIXME this needs a better place

ABORT = 1
CONTINUE = 0

#-----------------------------------------------------------------------------#

class BetterAuiNotebook(AuiNotebook):
    # work with pages instead of freaking indexes.  seriously.

    def __init__(self, parent):
        AuiNotebook.__init__(self, parent=parent)

    def GetPage(self, page):
        if isinstance(page, int):
            return AuiNotebook.GetPage(self,page)

        idx = self.GetPageIndex(page)
        if idx == wx.NOT_FOUND: return idx
        return AuiNotebook.GetPage(self, idx)

    def SetSelection(self, page):
        if isinstance(page, int):
            return AuiNotebook.SetSelection(self, page)

        idx = self.GetPageIndex(page)
        if idx == wx.NOT_FOUND: return idx
        return AuiNotebook.SetSelection(self, idx)

    def __get_pages(self):
        """Iterable view of the pages in the notebook."""
        return (self.GetPage(i) for i in xrange(self.GetPageCount()))
    pages = property(fget=__get_pages)

    def __get_active_page(self):
        return self.GetPage(self.GetSelection())
    def __set_active_page(self, page_or_index):
        if isinstance(page_or_index, CPPStyledTextCtrl):
            page_or_index = self.GetPageIndex(page_or_index)
        self.SetSelection(page_or_index)
    active_page = property(fget=__get_active_page,fset=__set_active_page)

#----------------------------------------------------------------------------#-

class SketchFrame(wx.Frame, UserInterface):
    """wx.Frame for showing a sketch.

    If main_file is None, will make a new, unsaved sketch.

    Verify/etc. buttons, tabbed view of the files in the sketch, sketch
    status, window for compiler output, and last compile's exit status;
    i.e., it's mostly a rehash of the usual Wiring/Arduino interface.
    """

    def __init__(self, main_file=None, parent=None, id=wx.ID_ANY,
                 title=u"Maple IDE", pos=(50,50), size=(640,700),
                 style=wx.DEFAULT_FRAME_STYLE, name=u"Maple IDE"):
        basename = os.path.basename(main_file) if main_file else None
        title = u'Maple IDE | ' + basename if basename else u'Maple IDE'
        wx.Frame.__init__(self, parent, id, title, pos, size, style, name)

        self._pages = {}        # {basename: CPPStyledTextCtrl}
        self.modified = False   # are there unsaved changes?

        # this thing totally takes the pain out of panel layout
        self.__mgr = wx.aui.AuiManager(self)

        # menu bar
        self.menu_bar = self._make_menu_bar()
        self.SetMenuBar(self.menu_bar)

        # toolbar
        self._make_toolbar()

        # status bar
        self.CreateStatusBar()

        # tabbed view of current sketch
        # FIXME disallow closing of tabs -- might have to switch AUI
        # implementation
        self.nb = BetterAuiNotebook(self)
        # was trying this + SetCloseButton, but !@#$, it doesn't exist
        #                              style=wx.aui.AUI_NB_TOP | \
        #                                  wx.aui.AUI_NB_TAB_MOVE | \
        #                                  wx.aui.AUI_NB_CLOSE_ON_ALL_TABS)
        # print 'dir(self.nb):'
        # pprint(dir(self.nb))

        # subprocess (compiler/uploader) output goes here
        self.sub = wx.TextCtrl(self, -1, u'', wx.DefaultPosition,
                               wx.Size(200, 150),
                               wx.NO_BORDER | wx.TE_MULTILINE)
        comp_info = wx.aui.AuiPaneInfo()
        comp_info.Bottom()
        comp_info.CaptionVisible(True)
        comp_info.CloseButton(False)
        comp_info.Floatable(False)

        # add the panes to the manager
        self.__mgr.AddPane(self.nb, wx.CENTER)
        self.__mgr.AddPane(self.sub, info=comp_info)
        self.__mgr.Update()

        # set frame close handler
        self.Bind(wx.EVT_CLOSE, self.OnClose)

        # All set up, so initialize the sketch.  THIS MUST BE DONE AFTER
        # THE GUI GETS SET UP.
        if main_file is None: self.sketch = SB.fresh_sketch(self)
        else: self.sketch = Sketch(self, main_file)

        # the sketch setter calls CPPStyledTextCtrl.SetText, but we aren't
        # really modified yet, and we don't want the user to be able to
        # 'undo' the changes _we_ made by sticking the file contents into
        # our notebook's pages.
        self.not_really_modified()

        self.nb.active_page = self._pages[self.sketch.main_basename]


    #--------------------------- Menu bar creation ---------------------------#

    def _make_menu_bar(self):
        menu_bar = wx.MenuBar()

        ## convenience functions so we don't have to repeat ourselves x1e6
        def bind_handler(menu, text, handler):
            item = menu.Append(-1, text)
            self.Bind(wx.EVT_MENU, handler, item)
        def make_bind(menu):
            return lambda txt, handler: bind_handler(menu, txt, handler)

        ## File menu
        file_menu = wx.Menu()
        bind = make_bind(file_menu)

        # sketchbook submenu/bindings
        sketchbook_menu = wx.Menu()
        sketches = SB.sketch_dirs()
        open_sketch = lambda s: \
            lambda evt: self.OpenSketchNewFrame(SB.sketch_dir_get_abs(s))
        sketchbook_bind = make_bind(sketchbook_menu)
        for s in sketches: sketchbook_bind(s, open_sketch(s))
        # examples submenu/bindings
        examples_menu = wx.Menu()
        categories = EB.categories()
        open_example = lambda c,e: \
            lambda evt: self.OpenSketchNewFrame(EB.example_get_abs(c,e))
        for c in categories:
            cat_menu = wx.Menu()
            cat_bind = make_bind(cat_menu)
            for e in EB.category_examples(c):
                cat_bind(e, open_example(c, e))
            examples_menu.AppendMenu(-1, c, cat_menu)
        # file menu/bindings
        bind(u"&New\tCtrl-N", self.OnNewSketch)
        bind(u"&Open...\tCtrl-O", self.OnOpenSketch)
        file_menu.AppendMenu(-1, u"Sketchbook", sketchbook_menu)
        file_menu.AppendMenu(-1, u"Examples", examples_menu)
        bind(u"Close\tCTRL-W", self.OnClose)
        bind(u"&Save\tCTRL-S", self.OnSave)
        bind(u"S&ave As...\tSHIFT-CTRL-S", self.OnSaveAs)
        bind(u"&Upload to I/O Board\tCTRL-U", self.OnUpload)
        file_menu.AppendSeparator()
        bind(u"&Page Setup\tSHIFT-CTRL-P", self.OnPageSetup)
        bind(u"Print\tCTRL-P", self.OnPrint)

        menu_bar.Append(file_menu, "&File")

        ## Edit menu
        edit_menu = wx.Menu()
        bind = make_bind(edit_menu)

        bind(u"&Undo\tCTRL-Z", self.OnUndo)
        bind(u"&Redo\tCTRL-Y", self.OnRedo)
        edit_menu.AppendSeparator()
        bind(u"&Cut\tCtrl-X", self.OnCut)
        bind(u"C&opy\tCTRL-C", self.OnCopy)
        bind(u"Copy for &Forum\tSHIFT-CTRL-C", self.OnCopyForForum)
        bind(u"Copy as &HTML\tALT-CTRL-C", self.OnCopyAsHTML)
        bind(u"P&aste\tCTRL-V", self.OnPaste)
        bind(u"Select &All\tCTRL-A", self.OnSelectAll)
        edit_menu.AppendSeparator()
        bind(u"Co&mment/Uncomment\tCTRL-/", self.OnCommentUncomment)
        bind(u"&Increase Indent\tCTRL-]", self.OnIncreaseIndent)
        bind(u"&Decrease Indent\tCTRL-[", self.OnDecreaseIndent)
        edit_menu.AppendSeparator()
        bind(u"&Find\tCTRL-F", self.OnFind)
        bind(u"Find &Next\tCTRL-G", self.OnFindNext)

        menu_bar.Append(edit_menu, u"&Edit")

        ## Sketch menu
        sketch_menu = wx.Menu()
        bind = make_bind(sketch_menu)

        bind(u"&Verify / Compile\tCTRL-R", self.OnVerify)
        bind(u"&Stop", self.OnStop)
        sketch_menu.AppendSeparator()
        bind(u"S&how Sketch Folder\tCTRL-K", self.OnShowSketchFolder)
        bind(u"IMPORT LIBRARY SUBMENU", self.OnImportLibrary)
        bind(u"&Add File...", self.OnAddFile)

        menu_bar.Append(sketch_menu, u"&Sketch")

        ## Tools menu
        tools_menu = wx.Menu()
        bind = make_bind(tools_menu)

        bind(u"&Auto Format\tCTRL-T", self.OnAutoFormat)
        bind(u"A&rchive Sketch", self.OnArchiveSketch)
        bind(u"&Fix Encoding and Reload", self.OnFixEncodingAndReload)
        tools_menu.AppendSeparator()
        bind(u"&Serial Monitor\tSHIFT-CTRL-M", self.OnSerialMonitor)
        tools_menu.AppendSeparator()
        bind(u"BOARDS SUBMENU", self.OnBoardsSubmenu) # TODO
        bind(u"SERIAL PORT SUBMENU", self.OnSerialPortSubmenu) # TODO
        tools_menu.AppendSeparator()
        bind(u"BURN_BOOTLOADER", self.OnBurnBootloader) # TODO

        menu_bar.Append(tools_menu, u"&Tools")

        ## Help menu
        help_menu = wx.Menu()
        bind = make_bind(help_menu)

        bind(u"Getting Started", self.OnGettingStarted)
        bind(u"Development Environment", self.OnDevelopmentEnvironment)
        bind(u"Troubleshooting", self.OnTroubleshooting)
        bind(u"Language Reference", self.OnLanguageReference)
        bind(u"Visit Arduino.cc", self.OnVisitArduino)
        bind(u"Visit LeafLabs.com", self.OnVisitLeafLabs)

        menu_bar.Append(help_menu, u"&Help")

        return menu_bar

    #---------------------------- Toolbar creation ---------------------------#

    def _make_toolbar(self):
        self.toolbar = self.CreateToolBar()
        button_pieces = resources.desprite_bitmap(settings.TOOLBAR_BUTTONS, 7)
        verify, stop, new_sk, open_sk, save_sk, upload, serial = button_pieces
        self._add_to_toolbar(verify, self.OnVerify)
        self._add_to_toolbar(stop, self.OnStop)
        self._add_to_toolbar(new_sk, self.OnNewSketchToolbar)
        self._add_to_toolbar(open_sk, self.OnOpenSketchToolbar)
        self._add_to_toolbar(save_sk, self.OnSave)
        self._add_to_toolbar(upload, self.OnUpload)
        self._add_to_toolbar(serial, self.OnSerialMonitor)
        self.toolbar.Realize()

    def _add_to_toolbar(self, bitmap, click_handler):
        tool_id = wx.NewId()
        self.toolbar.SetToolBitmapSize(bitmap.GetSize())
        self.toolbar.AddTool(tool_id, bitmap)
        self.Bind(wx.EVT_TOOL, click_handler, id=tool_id)
        return tool_id

    #------------------------------- Properties ------------------------------#

    def __get_sketch(self):
        return self.__sketch
    def __set_sketch(self, sketch):
        self.__sketch = sketch
        self.redisplay(reset=True)
    sketch = property(fget=__get_sketch, fset=__set_sketch)

    #----------------------- File Menu event handlers ------------------------#

    def OnNewSketch(self, evt):
        make_sketch_frame()

    def OnOpenSketch(self, evt):
        path = self._query_user_sketch()
        if path is None: return
        self.OpenSketchNewFrame(path)

    def OnClose(self, evt):
        if self._query_user_save(u'closing') == ABORT:
            return
        self.sketch.cleanup()
        self.__mgr.UnInit()
        self.Destroy()

    def OnSave(self, evt):
        if not self.save(): self.OnSaveAs(evt)

    def OnSaveAs(self, evt):
        default_file = self.sketch.name or ""
        path = wx.FileSelector(u"Save Maple sketch as...",
                               default_path=settings.SKETCHBOOK_PATH,
                               default_filename=default_file,
                               flags=wx.FD_SAVE|wx.FD_OVERWRITE_PROMPT,
                               parent=self)
        if path == u"": return   # user hit cancel

        self.sketch.reset_directory(path, create=True)
        self.save()

    def OnUpload(self, evt):
        if self._query_user_save(u'uploading') == ABORT:
            return
        self.sketch.upload()

    def OnPageSetup(self, evt): # TODO
        not_implemented_popup()

    def OnPrint(self, evt): # TODO
        not_implemented_popup()

    #----------------------- Edit Menu event handlers ------------------------#

    # TODO? many of these are already keybindings in StyledTextCtrl;
    # maybe take this out and see if everything still works

    def OnUndo(self, evt):
        self.nb.active_page.Undo()

    def OnRedo(self, evt):
        self.nb.active_page.Redo()

    def OnCut(self, evt):
        self.nb.active_page.Cut()

    def OnCopy(self, evt):
        self.nb.active_page.Copy()

    def OnCopyForForum(self, evt): # TODO
        not_implemented_popup()

    def OnCopyAsHTML(self, evt): # TODO (use pygments!)
        not_implemented_popup()

    def OnPaste(self, evt):
        self.nb.active_page.Paste()

    def OnSelectAll(self, evt):
        self.nb.active_page.SelectAll()

    def OnCommentUncomment(self, evt):
        self.nb.active_page.ToggleCommentUncomment()

    def OnIncreaseIndent(self, evt):
        self.nb.active_page.IncreaseIndent()

    def OnDecreaseIndent(self, evt):
        self.nb.active_page.DecreaseIndent()

    def OnFind(self, evt): # TODO
        not_implemented_popup()

    def OnFindNext(self, evt): # TODO
        not_implemented_popup()

    #---------------------- Sketch Menu event handlers -----------------------#

    def OnVerify(self, evt):
        # FIXME need to communicate the various compliation settings
        # -- what board to use, RAM vs. FLASH, etc.  that means making
        # menus for them (see TODOs in _make_menu_bar), storing the
        # results, and passing them to compile.
        if self._query_user_save() == ABORT:
            return
        # the sketch will call back any results to display via
        # SketchFrame's UserInterface methods
        self.sketch.compile()

    def OnStop(self, evt):
        self.sketch.stop_compiling()

    def OnShowSketchFolder(self, evt): # TODO
        not_implemented_popup()

    def OnImportLibrary(self, evt): # TODO
        not_implemented_popup()

    def OnAddFile(self, evt): # TODO
        not_implemented_popup()

    #----------------------- Tools Menu event handlers -----------------------#

    def OnAutoFormat(self, evt): # TODO
        not_implemented_popup()

    def OnArchiveSketch(self, evt): # TODO
        #FIXME possible abstraction violation since import statement was needed
        date = unicode(datetime.datetime.now().strftime('_%b%d').lower())
        default_file = self.sketch.name + date + ".zip" or ""
        path = wx.FileSelector(u"Archive Sketch as:",
                               default_path=settings.SKETCHBOOK_PATH,
                               default_filename=default_file,
                               flags=wx.FD_SAVE|wx.FD_OVERWRITE_PROMPT,
                               parent=self)
        if path == u"": return  #user hit cancel

        self.sketch.archive(path)

    def OnFixEncodingAndReload(self, evt): # TODO
        not_implemented_popup()

    def OnSerialMonitor(self, evt): # TODO
        not_implemented_popup()

    def OnBoardsSubmenu(self, evt): # TODO
        not_implemented_popup()

    def OnSerialPortSubmenu(self, evt): # TODO
        not_implemented_popup()

    def OnBurnBootloader(self, evt): # TODO
        not_implemented_popup()

    #----------------------- Help menu event handlers ------------------------#

    def _open_url(self, url):
        # unspecified behavior when it's a file:// url, but it seems to work
        webbrowser.open_new_tab(url)

    def OnGettingStarted(self, evt):
        self._open_url(u'file://' + resources.reference(u'quickstart.html'))

    def OnDevelopmentEnvironment(self, evt):
        self._open_url(u'file://' + resources.reference(u'index.html'))

    def OnTroubleshooting(self, evt):
        self._open_url(u'file://' + \
                           resources.reference(u'troubleshooting.html'))

    def OnLanguageReference(self, evt):
        self._open_url(u'file://' + resources.reference(u'language.html'))

    def OnVisitArduino(self, evt):
        self._open_url(u'http://arduino.cc')

    def OnVisitLeafLabs(self, evt):
        self._open_url(u'http://leaflabs.com')

    #------------------------ Toolbar event handlers -------------------------#

    ## mostly don't need to be written.  all but these are taken care of
    ## by existing menu bar handlers.

    def OnNewSketchToolbar(self, evt):
        if self._query_user_save() == ABORT:
            return
        self.sketch = SB.fresh_sketch(self)

    def OnOpenSketchToolbar(self, evt):
        if self._query_user_save() == ABORT:
            return
        path = self._query_user_sketch()
        if path is None: return
        self.sketch = Sketch(self, path)
        self.SetTitle(u'MapleIDE | ' + self.sketch.name)
        self.not_really_modified()
        self.nb.active_page = self._pages[self.sketch.main_basename]

    #------------------------ UserInterface methods --------------------------#

    def show_warning(self, message, details):
        warning_popup(message, details)

    def show_error(self, message, details):
        error_popup(message, details)

    def redisplay(self, reset=False):
        """Redisplays.  If reset=True, wipes all the tabs and assumes that
        self.sketch is right about everything. Must be called after the
        sketch is set."""
        if self.sketch is None:
            raise RuntimeError("no sketch set")

        self.clear_subprocess_window()

        if reset:
            self._clear_tabs()
            # populate the notebook with pages from the sketch
            for basename, code in self.sketch.sources.iteritems():
                page = self.make_new_tab(basename)
                page.SetText(code.code)
                self._pages[basename] = page

        page_count = self.nb.GetPageCount()
        for basename, code in self.sketch.sources.iteritems():
            page = self._pages[basename]

            # add the page to the notebook if it doesn't exist, but we
            # really shouldn't have todo this.  (right now, this can only
            # happen if a user closes a tab, which mbolivar is trying to
            # disallow but hasn't found out how, yet).
            page_idx = self.nb.GetPageIndex(page)
            if page_idx == wx.NOT_FOUND:
                # TODO better error logging
                print u'WARNING: unknown basename', basename
                page = self.make_new_tab(basename)
            page_count -= 1

            page.SetText(code.code)

        if page_count != 0:
            # TODO better error logging
            print u'WARNING: page_count=%d, should be 0' % page_count

    def clear_subprocess_window(self):
        self.SetStatusText(u'')
        self.SetCaptionText(u'')
        self.sub.Clear()

    def append_subprocess_output(self, line):
        # TODO parse compiler error lines into clickable links
        self.sub.AppendText(line)

    def set_status(self, status, status_type):
        cap, low = status_type.capitalize(), status_type.lower()
        self.SetStatusText(u"%s exit status: %d" % (cap, status))
        if status == STATUS_SUCCESS:
            self.SetCaptionText(u'Finished with %s.' % low)
        else:
            self.SetCaptionText(u'%s was unsuccessful.' % cap)

    #------------------------- Other event handlers --------------------------#

    def OnTextChanged(self, evt):
        self.modified = True

    #--------------------- Unorganized auxiliary methods ---------------------#

    def make_new_tab(self, basename):
        page = CPPStyledTextCtrl(self.nb)
        self.Bind(wx.stc.EVT_STC_CHANGE, self.OnTextChanged, page)
        self.nb.AddPage(page, basename)
        return page

    def _clear_tabs(self):
        self._pages = {}
        for i in xrange(self.nb.GetPageCount()):
            # it's awesome that i have to do both of these, and that it's
            # undocumented.  awesome.
            self.nb.RemovePage(i)
            self.nb.DeletePage(i)
        assert self.nb.GetPageCount() == 0

    def SetCaptionText(self, text):
        # just stashing comp_info in __init__ won't work; i think
        # AuiManager makes a fresh AuiPaneInfo for any window you give it
        info = self.__mgr.GetPane(self.sub)
        info.Caption(text)
        self.__mgr.Update()

    def OpenSketchNewFrame(self, sketch_file):
        """Requires an absolute path to either a sketch main file, or a
        directory containing at least one such file.
        """
        if os.path.isdir(sketch_file):
            sketch_file = SB.sketch_main_file(sketch_file)
            if sketch_file is None:
                error_popup(u"Empty Sketch Directory",
                            u"Directory:\n\t%s\ncontains no %s files." % EXN)
                return

        x,y = self.GetScreenPositionTuple()
        # TODO smarter decision making on frame placement -- maybe making
        # it a child of this frame will DTRT?
        new_frame = SketchFrame(sketch_file, pos=(x+20,y+20))
        new_frame.Show(True)

    def _sync_sketch(self):
        mine, sketch = set(self._pages.keys()), set(self.sketch.sources.keys())
        if mine != sketch:      # can't happen
            raise MalformedSketchError(str(mine) + u' vs. ' + str(sketch))
        for basename, page in self._pages.iteritems():
            self.sketch.replace_source(basename, page.GetText())

    def save(self, message_on_error=True):
        self._sync_sketch()
        if self.sketch.save(message_on_error):
            SB.mark_saved(self.sketch)
            self.modified = False
            return True
        return False

    def _query_user_save(self, operation='continuing'):
        # use before operations that the user probably wants to have
        # saved before doing (compiling a sketch, closing a window,
        # etc.)  returns CONTINUE if you should go ahead and do it
       # (user said don't save/user said save and it worked), returns
        # ABORT otherwise.

        if not self.modified:
            return CONTINUE
        result = save_prompt_popup(u"There are unsaved changes",
                                   u"Save changes before %s?" % operation)
        if result == wx.ID_CANCEL:
            return ABORT
        elif result == wx.ID_YES:
            if self.save(): return CONTINUE
            else: return ABORT # something went wrong saving
        elif result == wx.ID_NO:
            return CONTINUE
        else:
            raise ValueError(result)

    def _query_user_sketch(self):
        dialog = wx.FileDialog(None, u"Open a Maple sketch...",
                               defaultDir=settings.SKETCHBOOK_PATH,
                               wildcard=u"*" + EXN,
                               style=wx.FD_FILE_MUST_EXIST | wx.FD_OPEN)
        if dialog.ShowModal() != wx.ID_OK: return None
        path = dialog.GetPath()
        dialog.Destroy()
        return path

    def not_really_modified(self):
        self.modified = False
        for page in self.nb.pages: page.EmptyUndoBuffer()

#-----------------------------------------------------------------------------#
