#!/usr/bin/env python
#
#   Copyright (C) 2008 Vytautas Saltenis.
#
# This file is part of Candy.
#
# Candy is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# Candy is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Candy. If not, see <http://www.gnu.org/licenses/>.
#

# If text interface will ever be needed, this one might be handy:
# http://freshmeat.net/projects/python-urwid/

import os
import time
import sys
import pdb
import platform
import subprocess

import wx
import wx.stc as stc
import wx.lib.pubsub as pubsub

if platform.system() == 'Windows':
    try:
        import win32api
    except ImportError:
        print 'You seem to be running Windows and don\'t have win32api.'
        print 'Tisk tisk tisk...'

import keyboard
import util
from status_line import StatusLine
import data
from constants import *


project_dir = os.path.dirname(__file__)
general_conf_path = os.path.join(project_dir, u'general.conf')
general_config = util.read_config(general_conf_path)
color_conf = os.path.join(project_dir, u'colorscheme-default.conf')
color_scheme = util.read_config(color_conf)


class VisualItem(object):
    """
    An item to hold visual representation. E.g. if the external item is a
    filename, this one will hold things like justified name, startChar in
    the ViewWindow coords and the like. Number of these objects is the number
    RawItems that actually fit on screen (at least partially).
    """
    def __init__(self):
        # Character on the row-representing string, which is the str[0]-th
        # char of this item's visual representation. Will not be negative,
        # since objects of this class represent only visible things, even
        # if only a part of the thing is visible
        self.start_char_on_line = 0

        # Length of the visible item in characters. Will be as much characters
        # as actually visible
        self.vis_len_in_chars = 0

        # The first byte in the string, representing the line that contains
        # this item. This is needed because of silly implementation detail
        # of STC: it needs to start (and apply) styling according to bytes,
        # not the characters. So for Unicode strings, I have to keep track
        # of bytes, not only characters.
        self.start_byte_on_line = 0

        # Length of the item's visual repr, expressed in bytes (same reasons
        # as with start_byte_on_line).
        self.vis_len_in_bytes = 0

        # Since objects of this class only represent things that are
        # on-screen, there's no need for special check. We only need to
        # record whether the whole item was fit to screen
        self.fully_in_view = False

    def set_start_byte(self, visible_text_line):
        chars_before_this_item = visible_text_line[:self.start_char_on_line]
        self.start_byte_on_line = len(chars_before_this_item.encode('utf-8'))


class SmartJustifier(object):
    def __init__(self, width):
        self.width = width
        self.num_dots = 3

    def justify(self, text):
        if len(text) <= self.width:
            return text.ljust(self.width)

        root, ext = os.path.splitext(text)
        new_width = self.width - self.num_dots

        if ext and ext != u'':
            new_width -= len(ext)

        if new_width <= 5:       # 5 = len('a...b')
            half_width_ceil = 1
            half_width_floor = 1
            ext_top = (self.width - half_width_ceil - half_width_floor -
                       self.num_dots)
        else:
            half_width_ceil = util.int_div_ceil(new_width, 2)
            half_width_floor = util.int_div_floor(new_width, 2)
            ext_top = len(ext)

        if ext_top > len(ext):
            half_width_ceil += ext_top - len(ext)

        dots = u'.' * self.num_dots
        left_part = root[:half_width_ceil]
        right_part = root[-half_width_floor:]
        new_text = left_part + dots + right_part + ext[:ext_top]

        return new_text


# The width/height/left/right are in characters
class ViewWindow(object):
    def __init__(self, width, height):
        # Number of characters that can fit in whole width of the pane
        self.width = width

        # Number of lines per single column
        self.height = height

        # How much characters to the right is the view window
        self.left = 0

        # Number of columns of items across all the width of the pane
        self.num_columns = 0

    def right(self):
        return self.left + self.width

    # only handles horizontal dimension
    def char_in_view(self, char_pos):
        return char_pos >= self.left and char_pos < self.right()


class PanelController(object):
    def __init__(self, parent, modelSignature, controllerSignature):
        self.model = data.PanelModel(modelSignature)
        self.controllerSignature = controllerSignature
        self.view = Panel(parent)
        self.bindEvents()
        signature = modelSignature + 'NEW ITEMS'
        pubsub.Publisher().subscribe(self.afterDirChange, signature)

        self.subscribe(self.searchCtrlEnter, 'CONTROL ENTER')
        self.subscribe(self.searchEnter, 'ENTER')
        self.subscribe(self.searchEscape, 'ESCAPE')
        self.subscribe(self.searchNewStatusLineText, 'NEW STATUS LINE TEXT')

        # String being searched incrementally
        self.searchStr = ''

        # Index of an item that is an accepted search match. Needed to know
        # which next match should be focused upon go-to-next-match
        self.searchMatchIndex = -1

        # Index of an item that is currently selected
        self.selectedItem = 0

        self.keys = keyboard.KeyboardConfig()
        self.keys.load(u'keys.conf', self)

    def subscribe(self, func, signature):
        msg = self.controllerSignature + signature
        pubsub.Publisher().subscribe(func, msg)

    def numItems(self):
        return len(self.model.items)

    # Used in tests
    def clearList(self):
        self.model.set_items([])
        self.selectedItem = 0
        self.view.num_full_columns = 0

    def initializeViewSettings(self, num_columns=3):
        self.view.initialize_view_settings(self.model.items, num_columns)
        self.view.highlight_search_matches(self.model.items, self.searchStr)
        self.setSelectionOnCurrItem()

    def initializeAndShowInitialView(self):
        self.initializeViewSettings()
        self.goHome()

        # This one is needed here to get the initial focus:
        self.view.SetFocus()

    def bindEvents(self):
        self.view.Bind(wx.EVT_CHAR, self.OnChar)
        self.view.Bind(wx.EVT_KEY_DOWN, self.OnKeyDown)
        self.view.Bind(wx.EVT_SET_FOCUS, self.OnSetFocus)

    def handleKeyEvent(self, keyCode, keyMod):
        func = self.keys.getFunc(keyCode, keyMod)

        if func:
            func()
            self.setSelectionOnCurrItem()

    def displaySelectionInfo(self):
        # in the line below, I'm subtracting 1 from number of items because
        # of '..' pseudoitem
        if self.numItems() > 0:
            item = self.getSelection()
            statusText = u'[Folder view]: %s\t%d item(s) -- \'%s\' in %s' \
                         % (os.getcwdu(), self.numItems() - 1,
                            item.file_name, item.path)
            self.view.get_frame().status_bar.SetStatusText(statusText)

    def OnKeyDown(self, evt):
        keyCode = evt.GetKeyCode()
        keyMod = evt.GetModifiers()
        self.handleKeyEvent(keyCode, keyMod)

    def OnChar(self, evt):
        keyCode = evt.GetKeyCode()
        self.handleKeyEvent(keyCode, None)

    def OnSetFocus(self, evt):
        self.view.on_set_focus()
        os.chdir(self.model.working_dir)

    def quiter(self):
        sys.exit(0)

    def updateView(self):
        self.view.update_display_by_items(self.model.items)

    def updir(self):
        self.selectedItem = 0
        self.clearScreen()
        self.selectedItem = self.model.updir()

    def listDriveLetters(self):
        if platform.system() != 'Windows':
            return

        self.selectedItem = 0
        self.model.set_items(data.collect_drive_letters())

    def flattenDirectory(self):
        self.model.flatten_directory()
        self.model.fill_list_by_working_dir(self.model.working_dir)

    def changeDir(self, fullPath, searchStr=u''):
        self.model.set_dir_filter(searchStr)
        os.chdir(fullPath)
        self.clearScreen()
        self.selectedItem = 0
        self.model.fill_list_by_working_dir(fullPath)

    def listSearchMatches(self, searchStr):
        self.changeDir(self.model.working_dir, searchStr)

    def downdir(self, dirName):
        self.changeDir(os.path.join(self.model.working_dir, dirName))

    def goHome(self):
        self.changeDir(os.path.expanduser(u'~'))

    def afterDirChange(self, message):
        self.updateView()
        self.setSelectionOnCurrItem()

    def searchCtrlEnter(self, msg):
        self.view.SetFocus()
        self.listSearchMatches(self.searchStr)

    def searchEnter(self, msg):
        self.view.SetFocus()
        # Here we want to stop searching and set focus on first search match.
        # But if there was no match, we want to behave more like when we cancel
        # search. Except we've no matches to clear, since no match means
        # nothing was highlighted
        if self.searchMatchIndex != -1:
            self.selectedItem = self.searchMatchIndex
            self.setSelectionOnCurrItem()

    def searchEscape(self, msg):
        self.view.SetFocus()
        self.view.apply_default_styles(self.model.items)  # clean matches

    def searchNewStatusLineText(self, msg):
        self.searchStr = msg.data
        self.searchMatchIndex = self.incrementalSearch(self.searchStr)

    def onEnter(self):
        selection = self.getSelection()

        if selection.is_dir:
            if selection.file_name == u'..':
                self.updir()
            else:
                self.downdir(selection.file_name)
        else:
            base, ext = os.path.splitext(selection.file_name)
            commandLine = util.resolve_command_by_file_ext(ext[1:].lower())

            if commandLine:
                subprocess.call([commandLine, selection.file_name])

    def clearScreen(self):
        self.view.clear_screen()

    def onNextMatch(self):
        item = self.selectedItem + 1
        self.searchMatchIndex = self.model.next_search_match(self.searchStr,
                                                             item)
        self.selectedItem = self.searchMatchIndex

    def incrementalSearch(self, searchStr):
        matchIndex = self.model.next_search_match(searchStr, self.selectedItem)
        self.view.move_item_into_view(self.model.items, matchIndex)
        self.view.highlight_search_matches(self.model.items, searchStr)
        return matchIndex

    def onStartIncSearch(self):
        self.searchStr = ''
        self.view.get_frame().status_line.SetText(u'/')
        self.view.get_frame().status_line.GotoPos(1)
        self.view.get_frame().status_line.SetFocus()

    def setSelectionOnCurrItem(self):
        if self.numItems() <= 0:
            return

        item = self.getSelection()
        if not item.visual_item or not item.visual_item.fully_in_view:
            self.view.move_item_into_view(self.model.items, self.selectedItem)
            self.view.highlight_search_matches(self.model.items, self.searchStr)

        self.view.set_selection_on_item(item)
        self.displaySelectionInfo()

    def moveSelectionDown(self):
        self.selectedItem += 1

        if self.selectedItem >= self.numItems():
            self.selectedItem = 0

    def moveSelectionUp(self):
        self.selectedItem -= 1

        if self.selectedItem < 0:
            self.selectedItem = self.numItems() - 1

        # This can happen if self.model.items is empty
        if self.selectedItem < 0:
            self.selectedItem = 0

    def moveSelectionLeft(self):
        self.selectedItem -= self.view.view_window.height

        if self.numItems() == 0:
            self.selectedItem = 0
            return

        if self.selectedItem < 0:
            # undo the decrement and start calculating from scratch:
            self.selectedItem += self.view.view_window.height

            # Avoiding too long line here... but...
            # TODO: figure out how to deal with that long line without
            # splitting. It suggests some nasty coupling.
            selItem = self.selectedItem
            numItems = self.numItems()
            selItem = self.view.update_selected_item_left(selItem, numItems)
            self.selectedItem = selItem

        if self.selectedItem == -1:
            self.selectedItem = self.numItems() - 1

    def moveSelectionRight(self):
        self.selectedItem += self.view.view_window.height

        if self.numItems() == 0:
            self.selectedItem = 0
            return

        if self.selectedItem > self.numItems():
            self.selectedItem -= self.view.view_window.height
            self.selectedItem %= self.view.view_window.height
            self.selectedItem += 1

        if self.selectedItem == self.numItems():
            self.selectedItem = 0

    def moveSelectionZero(self):
        self.selectedItem = 0

    def moveSelectionLast(self):
        self.selectedItem = self.numItems() - 1

        if self.selectedItem < 0:
            self.selectedItem = 0

    def startEditor(self):
        subprocess.call([u'gvim', self.getSelection().file_name])

    def refresh(self):
        backup = self.selectedItem
        self.changeDir(self.model.working_dir)
        self.view.highlight_search_matches(self.model.items, self.searchStr)
        self.selectedItem = backup

    def getSelection(self):
        return self.model.items[self.selectedItem]

    def startViewer(self):
        import viewr
        file = self.getSelection().file_name
        wnd = viewr.BuiltinViewerFrame(self.view, -1, file, file)
        wnd.Show(True)

    def switchPane(self):
        self.view.get_frame().switch_pane()
        self.afterDirChange(None)

    def switchSplittingMode(self):
        self.view.switch_splitting_mode()


class Panel(stc.StyledTextCtrl):
    def __init__(self, parent):
        stc.StyledTextCtrl.__init__(self, parent)

        # No margins and scroll bars over here!
        self.SetMarginWidth(1, 0)
        self.SetUseHorizontalScrollBar(0)

        self._bind_events()
        self._set_styles()

        self.view_window = None

        # Number of characters per column width
        self._chars_per_col = 0

        # Number of columns in the whole-wide view, that are filled from top
        # to bottom
        self.num_full_columns = 0

        # A set of VisualItems that are referenced from subset of
        # controller.items and represent visible parts of them on screen.
        self.visual_items = []

        # List of full-width lines, containing the text of the items.
        # Only sublines of these lines are displayed both for performance
        # reasons and to bypass a bug in STC, failing to display extremely
        # long lines correctly.
        self._full_text_lines = []

    def _bind_events(self):
        self.Bind(wx.EVT_WINDOW_DESTROY, self.on_destroy)
        self.Bind(wx.EVT_KILL_FOCUS, self.on_lose_focus)

    def _set_styles(self):
        # This repeats the default: the five bits are for styling, the rest
        # three are for indicators (like green squiggle line). I'm setting it
        # explicitly to have a reference to the starting point in the code if I
        # ever need some messing around with indicators.
        self.SetStyleBits(5)

        face_courier = general_config['font-face']
        pb = int(general_config['font-size'])
        size_and_face = 'size:%d,face:%s' % (pb, face_courier)

        # Set the styles according to color scheme
        style_spec = size_and_face + ',back:%s,fore:%s' \
                    % (color_scheme['background'], color_scheme['default-text'])
        self.StyleSetSpec(stc.STC_STYLE_DEFAULT, style_spec)
        self.StyleClearAll()
        style_spec = size_and_face + ',bold,fore:%s' % (color_scheme['folder'])
        self.StyleSetSpec(STYLE_FOLDER, style_spec)
        style_spec = size_and_face + ',bold,fore:%s,back:%s' \
                                     % (color_scheme['search-highlight-fore'],
                                        color_scheme['search-highlight-back'])
        self.StyleSetSpec(STYLE_INC_SEARCH, style_spec)
        self.SetSelBackground(1, color_scheme['selection-inactive'])
        self.SetSelForeground(1, color_scheme['selection-fore'])

    def initialize_view_settings(self, items, num_columns):
        width, height = self.GetClientSizeTuple()
        line_height = self.TextHeight(0)
        char_width = self.TextWidth(stc.STC_STYLE_DEFAULT, 'a')

        # Here view_window.left will be set to 0. Even if it's not,
        # it will be brought back to life when doing move_item_into_view:
        self.view_window = ViewWindow(width / char_width,
                                      height / line_height)
        self.view_window.num_columns = num_columns
        self._chars_per_col = width / char_width / self.view_window.num_columns
        self.clear_screen()
        self.update_display_by_items(items)

    def _set_debug_whitespace(self):
        if general_config['debug-whitespace'].lower() == 'true':
            self.SetViewWhiteSpace(stc.STC_WS_VISIBLEALWAYS)
            self.SetViewEOL(True)
        else:
            self.SetViewWhiteSpace(stc.STC_WS_INVISIBLE)
            self.SetViewEOL(False)

    def _create_visual_item(self, raw_item):
        row = raw_item.coords[1]
        vi = VisualItem()
        start_char_on_line = raw_item.start_char_on_line - self.view_window.left
        end_char_on_line = start_char_on_line + len(raw_item.visible_part)
        visible_line = self.GetLine(row)

        # Partially, to the left of ViewWindow:
        if start_char_on_line < 0 and end_char_on_line >= 0:
            raw_item_len = len(raw_item.visible_part)
            vi.vis_len_in_chars = start_char_on_line + raw_item_len
            vi.start_char_on_line = 0
            vi.set_start_byte(visible_line)
            tail = raw_item.visible_part[-vi.vis_len_in_chars:]
            vi.vis_len_in_bytes = len(tail.encode('utf-8'))
            vi.fully_in_view = False
            return vi

        # Partially, to the right of ViewWindow:
        if end_char_on_line >= self.view_window.width \
           and start_char_on_line < self.view_window.width:
            vi.start_char_on_line = start_char_on_line
            vi.vis_len_in_chars = self.view_window.width - vi.start_char_on_line
            vi.set_start_byte(visible_line)
            head = raw_item.visible_part[:vi.vis_len_in_chars]
            vi.vis_len_in_bytes = len(head.encode('utf-8'))
            vi.fully_in_view = False
            return vi

        # Fully in view:
        vi.start_char_on_line = start_char_on_line
        vi.vis_len_in_chars = len(raw_item.visible_part)
        vi.set_start_byte(visible_line)
        vi.vis_len_in_bytes = len(raw_item.visible_part.encode('utf-8'))
        vi.fully_in_view = True
        return vi

    def _extract_visual_item(self, item):
        item.visual_item = None
        is_in_view = self.view_window.char_in_view
        is_start_in_view = is_in_view(item.start_char_on_line)
        end_char_pos = item.start_char_on_line + len(item.visible_part)
        is_end_in_view = is_in_view(end_char_pos)

        if is_start_in_view or is_end_in_view:
            item.visual_item = self._create_visual_item(item)

    def _extract_visible_sublines(self):
        visible_sublines = []

        for line in self._full_text_lines:
            raw_subline = line[self.view_window.left : self.view_window.right()]
            subline = raw_subline.ljust(self.view_window.width)
            visible_sublines.append(subline)

        return u'\n'.join(visible_sublines).encode('utf-8')

    def _construct_full_text_lines(self, items):
        if self.view_window.height == 0:
            # Avoid division by zero
            self.view_window.height = 1

        self.num_full_columns = len(items) / self.view_window.height
        self._full_text_lines = ['' for i in range(self.view_window.height)]

        row = 0
        column = 0
        sj = SmartJustifier(self._chars_per_col - 1)

        for item in items:
            visible_part = sj.justify(item.file_name) + u' '
            item.coords =(column, row)
            item.start_char_on_line = len(self._full_text_lines[row])
            utf8_line = self._full_text_lines[row].encode('utf-8')
            item.start_byte_on_line = len(utf8_line)
            item.visible_part = visible_part
            self._full_text_lines[row] += visible_part
            row += 1

            if row > self.view_window.height - 1:
                row = 0
                column += 1

    def update_display_by_items(self, raw_items,
                                construct_full_text_lines=True):
        self.clear_screen()
        self.SetReadOnly(False)

        if construct_full_text_lines:
            self._construct_full_text_lines(raw_items)

        self.SetTextUTF8(self._extract_visible_sublines())
        self.visual_items = map(self._extract_visual_item, raw_items)
        self.EmptyUndoBuffer()
        self.SetReadOnly(True)
        self._set_debug_whitespace()
        self.apply_default_styles(raw_items)

    def get_frame(self):
        return self.GetParent().GetParent()

    def on_destroy(self, evt):
        # This is how the clipboard contents can be preserved after
        # the app has exited.
        wx.TheClipboard.Flush()
        evt.Skip()

    def clear_screen(self):
        self.SetReadOnly(False)
        self.ClearAll()
        self.SetReadOnly(True)

    def switch_splitting_mode(self):
        self.get_frame().switch_splitting_mode()

    def on_set_focus(self):
        self.SetSelBackground(1, color_scheme['selection-back'])
        self.SetSelForeground(1, color_scheme['selection-fore'])

    def on_lose_focus(self, evt):
        self.SetSelBackground(1, color_scheme['selection-inactive'])
        self.SetSelForeground(1, color_scheme['selection-fore'])

    def highlight_search_matches(self, items, search_str):
        self.apply_default_styles(items)
        search_str_lower = search_str.lower()

        for i in items:
            if i.visual_item:
                match_offset = i.file_name.lower().find(search_str_lower)

                if match_offset != -1:
                    end_of_highlight = i.visual_item.vis_len_in_chars
                    if match_offset + len(search_str) > end_of_highlight:
                        # TODO: this is a temporary hack to make the highlight
                        # always fit the visible part of an item. As we must
                        # run the search through the actual filename by
                        # definition, this match offset can be way off the
                        # visible part of an item. This issue of highlighting a
                        # search match inside the invisible part of a file name
                        # needs to be addressed separately, but for now it will
                        # suffice to make it less visually disturbing.
                        match_offset = 0

                    selection_start = (self._get_item_start_byte(i) +
                                       match_offset)

                    # Set the style for the new match:
                    self.StartStyling(selection_start, 0xff)
                    stylingRegion = len(search_str.encode('utf-8'))
                    self.SetStyling(stylingRegion, STYLE_INC_SEARCH)

    def move_item_into_view(self, items, index):
        item = items[index]
        start_char_on_line = item.start_char_on_line
        end_char_on_line = start_char_on_line + len(item.visible_part)

        if start_char_on_line < self.view_window.left:
            # move view window left
            self.view_window.left = start_char_on_line
        elif end_char_on_line > self.view_window.right():
            # move view window right
            self.view_window.left = end_char_on_line - self.view_window.width
        else:
            return      # The item is already in view

        self.update_display_by_items(items, False)

    def set_selection_on_item(self, item):
        selection_start = self._get_item_start_byte(item)
        self.SetCurrentPos(selection_start)
        self.EnsureCaretVisible()

        if item and item.visual_item:
            num_chars_to_select = item.visual_item.vis_len_in_bytes
        else:
            num_chars_to_select = self._chars_per_col

        selection_len = selection_start + num_chars_to_select
        self.SetSelection(selection_start, selection_len)

    def update_selected_item_left(self, selected_item, num_items):
        num_full_lines = num_items % self.view_window.height
        num_full_columns = self.num_full_columns + 1
        bottom_right_index = self.view_window.height * num_full_columns
        bottom_right_index -= 1

        if selected_item % self.view_window.height > num_full_lines:
            bottom_right_index = self.view_window.height * self.num_full_columns
            bottom_right_index -= 1

        return selected_item - self.view_window.height + bottom_right_index

    def _get_item_start_byte(self, item):
        # -1 below because I want to get byte count for the lines [0..currLine)
        row = item.coords[1] - 1
        sum_bytes = 0

        if row >= 0:
            # +1 below because GetLineEndPosition doesn't account for newlines
            # TODO: why not +row? If it skips newlines, it should have
            # skipped N (=row) of them
            sum_bytes = self.GetLineEndPosition(row) + 1

        start_byte_on_line = 0

        if item.visual_item:
            start_byte_on_line = item.visual_item.start_byte_on_line

        return sum_bytes + start_byte_on_line

    def apply_default_styles(self, raw_items):
        for index, item in enumerate(raw_items):
            if item.visual_item:
                sel_start = self._get_item_start_byte(item)

                # Note the 0x1f. It means I'm only affecting the style
                # bits, leaving the indicators alone. This avoids having
                # the nasty green squiggle underline.
                self.StartStyling(sel_start, 0x1f)

                item_name_len = item.visual_item.vis_len_in_bytes
                self.SetStyling(item_name_len, item.style)


class Candy(wx.Frame):
    def __init__(self, parent, id, title):
        wx.Frame.__init__(self, parent, -1, title)

        self.splitter = wx.SplitterWindow(self, ID_SPLITTER,
                                          style=wx.SP_BORDER)
        self.splitter.SetMinimumPaneSize(50)

        display_size = wx.DisplaySize()
        app_size = (display_size[0] / 2, display_size[1] / 2)
        self.SetSize(app_size)

        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.sizer.Add(self.splitter, 1, wx.EXPAND)
        self.status_line = StatusLine(self, ID_STATUS_LINE, app_size[0],
                                      general_config, color_scheme)
        self.sizer.AddSpacer(2)
        sizer_flags = wx.BOTTOM | wx.ALIGN_BOTTOM | wx.EXPAND
        self.sizer.Add(self.status_line, 0, sizer_flags)
        self.SetSizer(self.sizer)

        self.p1 = PanelController(self.splitter, 'm1.', 'c1.')
        self.p2 = PanelController(self.splitter, 'm2.', 'c2.')
        self.splitter.SplitVertically(self.p1.view, self.p2.view)

        self.Bind(wx.EVT_SIZE, self.on_size)
        self.Bind(wx.EVT_SPLITTER_DCLICK, self.on_double_click, id=ID_SPLITTER)
        self.Bind(wx.EVT_SPLITTER_SASH_POS_CHANGED, self.on_sash_pos_changed,
                  id=ID_SPLITTER)

        self.status_bar = self.CreateStatusBar()
        self.status_bar.SetStatusText(os.getcwdu())
        self.Center()
        self.set_active_pane(self.p1)

    def set_active_pane(self, pane):
        self.active_pane = pane
        pane.view.SetFocus()
        self.status_line.set_message_prefix(pane.controllerSignature)

    def setup_and_show(self):
        self.p2.initializeAndShowInitialView()
        self.p1.initializeAndShowInitialView()
        self.set_active_pane(self.p1)

    # XXX: is it ever used?
    def OnExit(self, e):
        self.Close(True)

    def update_panes_on_size(self):
        num_columns = 3

        if self.splitter.GetSplitMode() == wx.SPLIT_HORIZONTAL:
            num_columns = 5

        self.p1.initializeViewSettings(num_columns)
        self.p2.initializeViewSettings(num_columns)

    def split_equal(self):
        size = self.GetSize()

        split_mode = self.splitter.GetSplitMode()
        sash_dimension = size.x

        if split_mode == wx.SPLIT_HORIZONTAL:
            sash_dimension = size.y

        # compensate for the five pixels of sash itself (dammit!)
        sash_dimension -= 5
        self.splitter.SetSashPosition(sash_dimension / 2)
        self.update_panes_on_size()

    def on_size(self, event):
        self.split_equal()
        event.Skip()

    def on_double_click(self, event):
        self.split_equal()

    def on_sash_pos_changed(self, event):
        self.splitter.UpdateSize()
        self.update_panes_on_size()
        event.Skip()

    def switch_pane(self):
        if self.active_pane == self.p1:
            self.set_active_pane(self.p2)
        else:
            self.set_active_pane(self.p1)

    def switch_splitting_mode(self):
        curr_split_mode = self.splitter.GetSplitMode()
        new_split_mode = wx.SPLIT_VERTICAL
        num_columns = 3

        if curr_split_mode == wx.SPLIT_VERTICAL:
            new_split_mode = wx.SPLIT_HORIZONTAL
            num_columns = 5

        self.splitter.SetSplitMode(new_split_mode)
        self.split_equal()
        self.p1.initializeViewSettings(num_columns)
        self.p2.initializeViewSettings(num_columns)


def main():
    app = wx.App(0)
    candy = Candy(None, -1, 'Candy')
    candy.Show()
    candy.setup_and_show()
    app.MainLoop()


if __name__ == '__main__':
    main()

