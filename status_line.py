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
        self.messagePrefix = ''
        self.SetMarginWidth(1, 0)
        self.SetUseHorizontalScrollBar(0)

        faceCourier = config['font-face'] # 'Courier'
        pb = int(config['font-size']) # 12

        # Set the styles according to color scheme
        styleSpec = 'size:%d,face:%s,back:%s,fore:%s' \
                    % (pb, faceCourier, color_scheme['background'],
                       color_scheme['default-text'])
        self.StyleSetSpec(stc.STC_STYLE_DEFAULT, styleSpec)
        self.StyleClearAll()

        self.Bind(stc.EVT_STC_MODIFIED, self.on_status_line_change)
        self.Bind(wx.EVT_KEY_DOWN, self.on_key_down)

    def on_key_down(self, evt):
        keyCode = evt.GetKeyCode()
        keyMod = evt.GetModifiers()

        if not self.process_key_event(keyCode, keyMod):
            evt.Skip()

    def process_key_event(self, keyCode, keyMod):
        message = self.messagePrefix

        if keyCode == wx.WXK_RETURN:
            if keyMod == wx.MOD_CONTROL:
                message += 'CONTROL '
            message += 'ENTER'
        elif keyCode == wx.WXK_ESCAPE:
            message += 'ESCAPE'
        elif keyCode == wx.WXK_BACK:
            text = self.GetText()
            if text and text == u'/':
                message += 'ESCAPE'

        if message != self.messagePrefix:
            text = self.GetText()
            self.ClearAll()
            pubsub.Publisher().sendMessage(message, text[1:])
            return True

        return False

    def on_status_line_change(self, evt):
        type = evt.GetModificationType()

        if stc.STC_MOD_BEFOREINSERT & type != 0 \
           or stc.STC_MOD_BEFOREDELETE & type != 0:
            return

        message = self.messagePrefix + 'NEW STATUS LINE TEXT'
        text = self.GetText()

        if text != '':
            pubsub.Publisher().sendMessage(message, text[1:])

