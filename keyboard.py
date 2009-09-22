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
        self.key_code = 0
        self.mod_ctrl = False
        self.mod_alt = False
        self.mod_shift = False

    def modifiers_bit_mask(self):
        mask = 0

        if self.mod_ctrl:
            mask |= wx.MOD_CONTROL

        if self.mod_shift:
            mask |= wx.MOD_SHIFT

        if self.mod_alt:
            mask |= wx.MOD_ALT

        return mask

    def parse(self, str):
        if len(str) == 1:
            self._parse_len_one(str)
        elif str.lower() == 'esc':
            self.key_code = wx.WXK_ESCAPE
        elif str.lower() == 'space':
            self.key_code = wx.WXK_SPACE
        elif str.lower() == 'tab':
            self.key_code = wx.WXK_TAB
        elif str.lower() in ['enter', 'return']:
            self.key_code = wx.WXK_RETURN
        elif str.lower().startswith('f') and len(str) > 1:
            self._parse_function_keys(str)
        else:
            self._parse_complex(str)

    def _parse_function_keys(self, str):
        try:
            number = eval(str[1:])
        except:
            raise EventParseError(str)

        funcs = [wx.WXK_F1, wx.WXK_F2, wx.WXK_F3, wx.WXK_F4, wx.WXK_F5,
                 wx.WXK_F6, wx.WXK_F7, wx.WXK_F8, wx.WXK_F9, wx.WXK_F10,
                 wx.WXK_F11, wx.WXK_F12, wx.WXK_F13, wx.WXK_F14, wx.WXK_F15,
                 wx.WXK_F16, wx.WXK_F17, wx.WXK_F18, wx.WXK_F19, wx.WXK_F20,
                 wx.WXK_F21, wx.WXK_F22, wx.WXK_F23, wx.WXK_F24]
        self.key_code = funcs[number - 1]

    def _parse_complex(self, str):
        parts = str.split('-')

        if len(parts) <= 1:
            raise EventParseError(str)

        if parts[0] == 'C':
            self.mod_ctrl = True
        elif parts[0] == 'S':
            self.mod_shift = True
        elif parts[0] in ['A', 'M']:
            self.mod_alt = True
        else:
            raise EventParseError(str)

        self.parse('-'.join(parts[1:]))

    def _parse_len_one(self, str):
        if str in 'ABCDEFGHIJKLMNOPQRSTUVWZYX':
            self.char = str
            self.key_code = ord(str)
            self.mod_shift = True
            return
        elif str in 'abcdefghijklmnopqrstuvwzyx':
            self.char = str
            self.key_code = ord(str.upper())
            return
        elif str in '0123456789`-=[]\\;\',./':
            self.char = str
            self.key_code = ord(str)
            return
        elif str in '!@#$%^&*()~_+{}|:"<>?':
            self.char = str
            self.key_code = ord(str)
            self.mod_shift = True
            return


def split_left_colon(line):
    sline = line.strip()
    colon_index = sline.find(':')

    if colon_index == -1:
        return line

    return (sline[:colon_index], sline[colon_index + 1:])


class KeyboardConfig(object):
    def __init__(self):
        self.events = {}

    def get_func(self, key_code, key_mod):
        for e in self.events:
            if key_code == e.key_code:
                if not key_mod:
                    return self.events[e]

                if key_mod == e.modifiers_bit_mask():
                    return self.events[e]

        return None

    def _parse_bindings(self, command, bindings):
        bs = bindings.split(',')
        events = []

        for b in bs:
            event = KeyboardEvent(command)
            event.parse(b.strip())
            events.append(event)

        return events

    def load(self, file_name, panel):
        project_dir = os.path.dirname(__file__)
        keys_conf_path = os.path.join(project_dir, file_name)
        lines = open(keys_conf_path).readlines()

        for line in lines:
            if line.strip() == '':
                continue

            command, bindings = split_left_colon(line)
            for e in self._parse_bindings(command, bindings):
                try:
                    func = eval('panel.' + e.command)
                    self.events.setdefault(e, func)
                except AttributeError:
                    err_str = 'Key binding error: no such command "'
                    err_str += e.command + '"'
                    print err_str

