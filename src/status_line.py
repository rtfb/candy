#!/usr/bin/env python
#
#   Copyright (C) 2009 Vytautas Saltenis.
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

import wx
import wx.stc as stc
import wx.lib.pubsub as pubsub


class StatusLine(stc.StyledTextCtrl):
    def __init__(self, parent, id, width, config, color_scheme):
        stc.StyledTextCtrl.__init__(self, parent, id, size=(width, 20))
        self._message_prefix = ''
        self.SetMarginWidth(1, 0)
        self.SetUseHorizontalScrollBar(0)

        face_courier = config['font-face']
        pb = int(config['font-size'])

        # Set the styles according to color scheme
        style_spec = 'size:%d,face:%s,back:%s,fore:%s' \
                     % (pb, face_courier, color_scheme['background'],
                        color_scheme['default-text'])
        self.StyleSetSpec(stc.STC_STYLE_DEFAULT, style_spec)
        self.StyleClearAll()
        self.SetCaretForeground(color_scheme['default-text'])
        self.SetCaretWidth(3)

        self.Bind(stc.EVT_STC_MODIFIED, self.on_status_line_change)
        self.Bind(wx.EVT_KEY_DOWN, self.on_key_down)

    def set_message_prefix(self, prefix):
        self._message_prefix = prefix

    def on_key_down(self, event):
        key_code = event.GetKeyCode()
        key_mod = event.GetModifiers()

        if not self.process_key_event(key_code, key_mod):
            event.Skip()

    def process_key_event(self, key_code, key_mod):
        message = self._message_prefix

        if key_code == wx.WXK_RETURN:
            if key_mod == wx.MOD_CONTROL:
                message += 'CONTROL '
            message += 'ENTER'
        elif key_code == wx.WXK_ESCAPE:
            message += 'ESCAPE'
        elif key_code == wx.WXK_BACK:
            text = self.GetText()
            if text and text == u'/':
                message += 'ESCAPE'

        if message != self._message_prefix:
            text = self.GetText()
            self.ClearAll()
            pubsub.Publisher().sendMessage(message, text[1:])
            return True

        return False

    def on_status_line_change(self, event):
        type = event.GetModificationType()

        if stc.STC_MOD_BEFOREINSERT & type != 0 \
           or stc.STC_MOD_BEFOREDELETE & type != 0:
            return

        message = self._message_prefix + 'NEW STATUS LINE TEXT'
        text = self.GetText()

        if text != '' and text.startswith(u'/'):
            pubsub.Publisher().sendMessage(message, text[1:])

    def start_typing(self, prefix):
        self.SetText(prefix)
        self.GotoPos(1)
        self.SetFocus()

