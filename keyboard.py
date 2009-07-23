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

# Keyboard Binding Handler

import os
import exceptions

import wx


class EventParseError(exceptions.Exception):
    def __init__(self, eventStr):
        self.eventStr = eventStr

    def __str__(self):
        return 'Failed to parse event \'%s\'' % (self.eventStr)


class KeyboardEvent(object):
    def __init__(self, command=''):
        self.reset()
        self.command = command

    def reset(self):
        self.char = ''
        self.keyCode = 0
        self.modCtrl = False
        self.modAlt = False
        self.modShift = False

    def modifiersBitMask(self):
        mask = 0

        if self.modCtrl:
            mask |= wx.MOD_CONTROL

        if self.modShift:
            mask |= wx.MOD_SHIFT

        if self.modAlt:
            mask |= wx.MOD_ALT

        return mask

    def parse(self, str):
        if len(str) == 1:
            self._parseLenOne(str)
        elif str.lower() == 'esc':
            self.keyCode = wx.WXK_ESCAPE
        elif str.lower() == 'space':
            self.keyCode = wx.WXK_SPACE
        elif str.lower() == 'tab':
            self.keyCode = wx.WXK_TAB
        elif str.lower() in ['enter', 'return']:
            self.keyCode = wx.WXK_RETURN
        elif str.lower().startswith('f') and len(str) > 1:
            self._parseFunctionKeys(str)
        else:
            self._parseComplex(str)

    def _parseFunctionKeys(self, str):
        try:
            number = eval(str[1:])
        except:
            raise EventParseError(str)

        funcs = [wx.WXK_F1, wx.WXK_F2, wx.WXK_F3, wx.WXK_F4, wx.WXK_F5,
                 wx.WXK_F6, wx.WXK_F7, wx.WXK_F8, wx.WXK_F9, wx.WXK_F10,
                 wx.WXK_F11, wx.WXK_F12, wx.WXK_F13, wx.WXK_F14, wx.WXK_F15,
                 wx.WXK_F16, wx.WXK_F17, wx.WXK_F18, wx.WXK_F19, wx.WXK_F20,
                 wx.WXK_F21, wx.WXK_F22, wx.WXK_F23, wx.WXK_F24]
        self.keyCode = funcs[number - 1]

    def _parseComplex(self, str):
        parts = str.split('-')

        if len(parts) <= 1:
            raise EventParseError(str)

        if parts[0] == 'C':
            self.modCtrl = True
        elif parts[0] == 'S':
            self.modShift = True
        elif parts[0] in ['A', 'M']:
            self.modAlt = True
        else:
            raise EventParseError(str)

        self.parse('-'.join(parts[1:]))

    def _parseLenOne(self, str):
        if str in 'ABCDEFGHIJKLMNOPQRSTUVWZYX':
            self.char = str
            self.keyCode = ord(str)
            self.modShift = True
            return
        elif str in 'abcdefghijklmnopqrstuvwzyx':
            self.char = str
            self.keyCode = ord(str.upper())
            return
        elif str in '0123456789`-=[]\\;\',./':
            self.char = str
            self.keyCode = ord(str)
            return
        elif str in '!@#$%^&*()~_+{}|:"<>?':
            self.char = str
            self.keyCode = ord(str)
            self.modShift = True
            return


class KeyboardConfig(object):
    def __init__(self):
        self.events = {}

    def getFunc(self, keyCode, keyMod):
        for e in self.events:
            if keyCode == e.keyCode:
                if not keyMod:
                    return self.events[e]

                if keyMod == e.modifiersBitMask():
                    return self.events[e]

        return None

    def _parseBindings(self, command, bindings):
        bs = bindings.split(',')
        events = []

        for b in bs:
            event = KeyboardEvent(command)
            event.parse(b.strip())
            events.append(event)

        return events

    def load(self, fileName, panel):
        projectDir = os.path.dirname(__file__)
        keysConfPath = os.path.join(projectDir, fileName)
        lines = open(keysConfPath).readlines()

        for line in lines:
            if line.strip() == '':
                continue

            command, bindings = line.strip().split(':')
            for e in self._parseBindings(command, bindings):
                try:
                    func = eval('panel.' + e.command)
                    self.events.setdefault(e, func)
                except AttributeError:
                    errStr = 'Key binding error: no such command "'
                    errStr += e.command + '"'
                    print errStr

