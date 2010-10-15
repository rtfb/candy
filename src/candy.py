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

wxVersion = wx.VERSION_STRING
if not wxVersion.startswith('2.8'):
    print "Can't run Candy! Need wxWidgets v2.8+, but got v" + wxVersion
    sys.exit(0)

import wx.stc as stc
import wx.lib.pubsub as pubsub

import keyboard
import util
from status_line import StatusLine
import data
from constants import *


project_dir = os.path.join(os.path.dirname(__file__), '..')
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


class LocationHistory:
    def __init__(self):
        self.container = []
        self.position = -1

    def __len__(self):
        return len(self.container)

    def push(self, path):
        if path == self.get():
            return

        self.container.append(path)
        self.position += 1

    def get(self):
        if len(self.container) == 0:
            return '~'

        return self.container[self.position]

    def back(self):
        self.position -= 1

        if self.position < 0:
            self.position = len(self.container) - 1

    def forth(self):
        self.position += 1

        if self.position >= len(self.container):
            self.position = 0


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
    def __init__(self, panel, model_signature, controller_signature):
        self.model = data.PanelModel(model_signature)
        self.controller_signature = controller_signature
        self.view = panel
        self._bind_events(self.view)
        signature = model_signature + 'NEW ITEMS'
        pubsub.Publisher().subscribe(self._after_dir_change, signature)

        self._subscribe(self._search_ctrl_enter, 'CONTROL ENTER')
        self._subscribe(self._search_enter, 'ENTER')
        self._subscribe(self._search_escape, 'ESCAPE')
        self._subscribe(self._search_new_status_line_text,
                        'NEW STATUS LINE TEXT')

        # String being searched incrementally
        self.search_str = ''

        # Index of an item that is an accepted search match. Needed to know
        # which next match should be focused upon go-to-next-match
        self.search_match_index = -1

        # Index of an item that is currently selected
        self.selected_item = 0

        self.keys = keyboard.KeyboardConfig()
        self.keys.load(u'keys.conf', self)

    def _subscribe(self, func, signature):
        msg = self.controller_signature + signature
        pubsub.Publisher().subscribe(func, msg)

    def _num_items(self):
        return len(self.model.items)

    # Used in tests
    def clear_list(self):
        self.model.set_items([])
        self.selected_item = 0
        self.view.num_full_columns = 0

    def initialize_view_settings(self, num_columns=3):
        self.view.initialize_view_settings(self.model.items, num_columns)
        self.view.highlight_search_matches(self.model.items, self.search_str)
        self._set_selection_on_curr_item()

    def initialize_and_show_initial_view(self):
        self.initialize_view_settings()
        self.go_home()

        # This one is needed here to get the initial focus:
        self.view.SetFocus()

    def _bind_events(self, view):
        view.Bind(wx.EVT_CHAR, self._on_char)
        view.Bind(wx.EVT_KEY_DOWN, self._on_key_down)
        view.Bind(wx.EVT_SET_FOCUS, self._on_set_focus)

    def _handle_key_event(self, key_code, key_mod):
        func = self.keys.get_func(key_code, key_mod)

        if func:
            func()
            self._set_selection_on_curr_item()

    def _display_selection_info(self):
        # in the line below, I'm subtracting 1 from number of items because
        # of '..' pseudoitem
        if self._num_items() > 0:
            item = self._get_selection()
            status_text = u'[Folder view]: %s\t%d item(s) -- \'%s\' in %s' \
                          % (os.getcwdu(), self._num_items() - 1,
                             item.file_name, item.path)
            self.view.get_frame().status_bar.SetStatusText(status_text)

    def _on_key_down(self, evt):
        key_code = evt.GetKeyCode()
        key_mod = evt.GetModifiers()
        self._handle_key_event(key_code, key_mod)

    def _on_char(self, evt):
        key_code = evt.GetKeyCode()
        self._handle_key_event(key_code, None)

    def _on_set_focus(self, evt):
        self.view.on_set_focus()
        os.chdir(self.model.working_dir)

    def quiter(self):
        sys.exit(0)

    def _update_view(self):
        self.view.update_display_by_items(self.model.items)

    def updir(self):
        self.selected_item = 0
        self.clear_screen()
        self.selected_item = self.model.updir()

    def list_drive_letters(self):
        if platform.system() != 'Windows':
            return

        self.selected_item = 0
        self.model.set_items(data.collect_drive_letters())

    def flatten_directory(self):
        self.model.flatten_directory()
        self.model.fill_list_by_working_dir(self.model.working_dir)

    def _change_dir(self, fullPath, search_str=u''):
        self.model.set_dir_filter(search_str)

        try:
            os.chdir(fullPath)
        except OSError, inst:
            self.view.set_status_line_text(str(inst))
            return

        self.clear_screen()
        self.selected_item = 0
        self.model.fill_list_by_working_dir(fullPath)

    def _list_search_matches(self, search_str):
        self._change_dir(self.model.working_dir, search_str)

    def downdir(self, dirName):
        self._change_dir(os.path.join(self.model.working_dir, dirName))

    def go_home(self):
        self._change_dir(os.path.expanduser(u'~'))

    def _after_dir_change(self, message):
        self._update_view()
        self._set_selection_on_curr_item()

    def _search_ctrl_enter(self, msg):
        self.view.SetFocus()
        self._list_search_matches(self.search_str)

    def _search_enter(self, msg):
        self.view.SetFocus()
        # Here we want to stop searching and set focus on first search match.
        # But if there was no match, we want to behave more like when we cancel
        # search. Except we've no matches to clear, since no match means
        # nothing was highlighted
        if self.search_match_index != -1:
            self.selected_item = self.search_match_index
            self._set_selection_on_curr_item()

    def _search_escape(self, msg):
        self.view.SetFocus()
        self.view.apply_default_styles(self.model.items)  # clean matches

    def _search_new_status_line_text(self, msg):
        self.search_str = msg.data
        self.search_match_index = self._incremental_search(self.search_str)

    def on_enter(self):
        selection = self._get_selection()

        if selection.is_dir:
            if selection.file_name == u'..':
                self.updir()
            else:
                self.downdir(selection.file_name)
        else:
            base, ext = os.path.splitext(selection.file_name)
            command_line = util.resolve_command_by_file_ext(ext[1:].lower())

            if command_line:
                subprocess.call([command_line, selection.file_name])

    def clear_screen(self):
        self.view.clear_screen()

    def on_next_match(self):
        item = self.selected_item + 1
        self.search_match_index = self.model.next_search_match(self.search_str,
                                                             item)
        self.selected_item = self.search_match_index

    def _incremental_search(self, search_str):
        match_index = self.model.next_search_match(search_str,
                                                   self.selected_item)
        self.view.move_item_into_view(self.model.items, match_index)
        self.view.highlight_search_matches(self.model.items, search_str)
        return match_index

    def on_start_inc_search(self):
        self.search_str = ''
        self.view.get_frame().status_line.start_typing(u'/')

    def on_start_command(self):
        self.command_str = ''
        self.view.get_frame().status_line.start_typing(u':')

    def _set_selection_on_curr_item(self):
        if self._num_items() <= 0:
            return

        item = self._get_selection()
        if not item.visual_item or not item.visual_item.fully_in_view:
            self.view.move_item_into_view(self.model.items, self.selected_item)
            self.view.highlight_search_matches(self.model.items,
                                               self.search_str)

        self.view.set_selection_on_item(item)
        self._display_selection_info()

    def move_selection_down(self):
        self.selected_item += 1

        if self.selected_item >= self._num_items():
            self.selected_item = 0

    def move_selection_up(self):
        self.selected_item -= 1

        if self.selected_item < 0:
            self.selected_item = self._num_items() - 1

        # This can happen if self.model.items is empty
        if self.selected_item < 0:
            self.selected_item = 0

    def move_selection_left(self):
        self.selected_item -= self.view.view_window.height

        if self._num_items() == 0:
            self.selected_item = 0
            return

        if self.selected_item < 0:
            # undo the decrement and start calculating from scratch:
            self.selected_item += self.view.view_window.height

            # Avoiding too long line here... but...
            # TODO: figure out how to deal with that long line without
            # splitting. It suggests some nasty coupling.
            selItem = self.selected_item
            num_items = self._num_items()
            selItem = self.view.update_selected_item_left(selItem, num_items)
            self.selected_item = selItem

        if self.selected_item == -1:
            self.selected_item = self._num_items() - 1

    def move_selection_right(self):
        self.selected_item += self.view.view_window.height

        if self._num_items() == 0:
            self.selected_item = 0
            return

        if self.selected_item > self._num_items():
            self.selected_item -= self.view.view_window.height
            self.selected_item %= self.view.view_window.height
            self.selected_item += 1

        if self.selected_item == self._num_items():
            self.selected_item = 0

    def move_selection_zero(self):
        self.selected_item = 0

    def move_selection_last(self):
        self.selected_item = self._num_items() - 1

        if self.selected_item < 0:
            self.selected_item = 0

    def start_editor(self):
        subprocess.call([u'gvim', self._get_selection().file_name])

    def refresh(self):
        backup = self.selected_item
        self._change_dir(self.model.working_dir)
        self.view.highlight_search_matches(self.model.items, self.search_str)
        self.selected_item = backup

    def _get_selection(self):
        return self.model.items[self.selected_item]

    def start_viewer(self):
        import viewr
        file = self._get_selection().file_name
        wnd = viewr.BuiltinViewerFrame(self.view, -1, file, file)
        wnd.Show(True)

    def switch_pane(self):
        self.view.get_frame().switch_pane()
        self._after_dir_change(None)

    def switch_splitting_mode(self):
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
            item.coords = (column, row)
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

    def set_status_line_text(self, text):
        self.get_frame().status_line.SetText(text)


class PanelSink:
    def __init__(self):
        pass

    def Bind(self, binder, func):
        pass

    def clear_screen(self):
        pass

    def update_display_by_items(self, foo):
        pass

    def set_status_line_text(self, text):
        pass


class Candy(wx.Frame):
    def __init__(self, parent, id, title):
        wx.Frame.__init__(self, parent, -1, title)

        self.splitter = wx.SplitterWindow(self, ID_SPLITTER,
                                          style=wx.SP_BORDER)
        self.splitter.SetMinimumPaneSize(50)

        width, height = wx.DisplaySize()
        self.SetSize((width / 2, height / 2))

        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.sizer.Add(self.splitter, 1, wx.EXPAND)
        self.status_line = StatusLine(self, ID_STATUS_LINE, width / 2,
                                      general_config, color_scheme)
        self.sizer.AddSpacer(2)
        sizer_flags = wx.BOTTOM | wx.ALIGN_BOTTOM | wx.EXPAND
        self.sizer.Add(self.status_line, 0, sizer_flags)
        self.SetSizer(self.sizer)

        self.p1 = PanelController(Panel(self.splitter), 'm1.', 'c1.')
        self.p2 = PanelController(Panel(self.splitter), 'm2.', 'c2.')
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
        self.status_line.set_message_prefix(pane.controller_signature)

    def setup_and_show(self):
        self.p2.initialize_and_show_initial_view()
        self.p1.initialize_and_show_initial_view()
        self.set_active_pane(self.p1)

    # XXX: is it ever used?
    def OnExit(self, e):
        self.Close(True)

    def update_panes_on_size(self):
        num_columns = 3

        if self.splitter.GetSplitMode() == wx.SPLIT_HORIZONTAL:
            num_columns = 5

        self.p1.initialize_view_settings(num_columns)
        self.p2.initialize_view_settings(num_columns)

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
        self.p1.initialize_view_settings(num_columns)
        self.p2.initialize_view_settings(num_columns)


def main():
    app = wx.App(0)
    candy = Candy(None, -1, 'Candy')
    candy.Show()
    candy.setup_and_show()
    app.MainLoop()


if __name__ == '__main__':
    main()

