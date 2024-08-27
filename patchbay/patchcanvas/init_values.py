#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# PatchBay Canvas engine using QGraphicsView/Scene
# Copyright (C) 2010-2019 Filipe Coelho <falktx@falktx.com>
# Copyright (C) 2019-2023 Mathieu Picot <picotmathieu@gmail.com>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of
# the License, or any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# For a full copy of the GNU General Public License see the doc/GPL.txt file.

from typing import TYPE_CHECKING, Iterator, Optional, Union
from enum import Enum, Flag, IntEnum, IntFlag, auto
import logging

from PyQt5.QtCore import QPointF, QRectF, QSettings, QPoint
from PyQt5.QtWidgets import QGraphicsItem

if TYPE_CHECKING:
    # all these classes are not importable normally because
    # it would make a circular import
    # they are imported only from IDE to get types
    from .theme import Theme
    from .theme_manager import ThemeManager
    from .scene import PatchScene
    from .box_widget import BoxWidget
    from .port_widget import PortWidget
    from .portgroup_widget import PortgroupWidget
    from .line_widget import LineWidget
    from .patchcanvas import CanvasObject
    from .hidden_conn_widget import HiddenConnWidget
    from .grouped_lines_widget import GroupedLinesWidget

_logger = logging.getLogger(__name__)

# Maximum Id for a plugin, treated as invalid/zero if above this value
MAX_PLUGIN_ID_ALLOWED = 0x7FF


class PortMode(IntFlag):
    NULL = 0x00
    INPUT = 0x01
    OUTPUT = 0x02
    BOTH = INPUT | OUTPUT
    
    def opposite(self) -> 'PortMode':
        if self is PortMode.INPUT:
            return PortMode.OUTPUT
        if self is PortMode.OUTPUT:
            return PortMode.INPUT
        if self is PortMode.BOTH:
            return PortMode.NULL
        if self is PortMode.NULL:
            return PortMode.BOTH
        return PortMode.NULL

    @staticmethod
    def in_out_both() -> Iterator['PortMode']:
        yield PortMode.INPUT
        yield PortMode.OUTPUT
        yield PortMode.BOTH


class PortType(IntFlag):
    NULL = 0x00
    AUDIO_JACK = 0x01
    MIDI_JACK = 0x02
    MIDI_ALSA = 0x04
    VIDEO = 0x08
    PARAMETER = 0x10


class PortSubType(IntFlag):
    '''a2j ports are MIDI ports, we only specify a decoration for them.
    CV ports are audio ports, but we prevent to connect an output CV port
    to a regular audio port to avoid material destruction, CV ports also
    look different, simply because this is absolutely not the same use.'''
    REGULAR = 0x01
    CV = 0x02
    A2J = 0x04


# Callback Actions
class CallbackAct(IntEnum):
    GROUP_INFO = auto()           # group_id: int
    GROUP_RENAME = auto()         # group_id: int
    GROUP_SPLITTED = auto()       # group_id: int
    GROUP_JOINED = auto()         # group_id: int
    GROUP_MOVE = auto()           # group_id: int, splitted_mode: PortMode, x: int, y: int
    GROUP_BOX_POS_CHANGED = auto()# group_id: int, port_mode: PortMode, box_pos: BoxPos
    GROUP_WRAP = auto()           # group_id: int, folded: bool
    GROUP_LAYOUT_CHANGE = auto()  # group_id: int, layout_mode: BoxLayoutMode, splitted_mode: PortMode
    GROUP_SELECTED = auto()       # group_id: int, splitted_mode: PortMode
    GROUP_HIDE_BOX = auto()       # group_id: int, port_mode: PortMode
    PORTGROUP_ADD = auto()        # group_id: int, port_mode: PortMode,
                                  #      port_type: PortType, port_ids: tuple[int]
    PORTGROUP_REMOVE = auto()     # group_id: int, portgrp_id: int
    PORT_INFO = auto()            # group_id: int, port_id: int
    PORT_RENAME = auto()          # group_id: int, port_id: int
    PORTS_CONNECT = auto()        # group_out_id: int, port_out_id: int,
                                  #      group_in_id: int, port_in_id: int
    PORTS_DISCONNECT = auto()     # conn_id: int
    GROUP_MENU_CALL = auto()      # group_id: int, port_mode: PortMode
    PORT_MENU_CALL = auto()       # group_id: int, port_id: int, connect_only: bool,
                                  #      x_pos: int, y_pos: int
    PORTGROUP_MENU_CALL = auto()  # group_id: int, portgrp_id: int, connect_only: bool,
                                  #      x_pos: int, y_pos: int
    PLUGIN_CLONE = auto()         # plugin_id: int
    PLUGIN_EDIT = auto()          # plugin_id: int
    PLUGIN_RENAME = auto()        # plugin_id: int
    PLUGIN_REPLACE = auto()       # plugin_id: int
    PLUGIN_REMOVE = auto()        # plugin_id: int
    PLUGIN_SHOW_UI = auto()       # plugin_id: int
    INLINE_DISPLAY = auto()       # plugin_id: int
    BG_RIGHT_CLICK = auto()       # 
    BG_DOUBLE_CLICK = auto()      # 
    CLIENT_SHOW_GUI = auto()      # group_id: int, visible: bool
    THEME_CHANGED = auto()        # theme_name: str
    ANIMATION_FINISHED = auto()


class BoxType(IntEnum):
    APPLICATION = 0
    HARDWARE = 1
    MONITOR = 2
    DISTRHO = 3
    FILE = 4
    PLUGIN = 5
    LADISH_ROOM = 6
    CLIENT = 7
    INTERNAL = 8


# inline display is not usable in RaySession or Patchance
# but this patchcanvas module has been forked from Carla
# and all about inline_display has been kept (we never know)
# but never tested.
class InlineDisplay(IntEnum):
    DISABLED = 0
    ENABLED = 1
    CACHED = 2


class BoxLayoutMode(IntEnum):
    'Define the way ports are put in a box'

    AUTO = 0
    '''Choose the layout between HIGH or LARGE
    within the box area.'''
    
    HIGH = 1
    '''In the case there are only INPUT or only OUTPUT ports,
    the title will be on top of the box.
    In the case there are both INPUT and OUTPUT ports,
    ports will be displayed from top to bottom, whatever they
    are INPUT or OUTPUT.'''
    
    LARGE = 2
    '''In the case there are only INPUT or only OUTPUT ports,
    the title will be on a side of the box.
    In the case there are both INPUT and OUTPUT ports,
    ports will be displayed in two columns, left for INPUT, 
    right for OUTPUT.'''


class BoxFlag(IntFlag):
    NONE = 0x00
    WRAPPED = auto()
    HIDDEN = auto()


class BoxHidding(Enum):
    'Enum used for animations where there are hidding or restoring boxes'
    
    NONE = auto()
    HIDDING = auto()
    RESTORING = auto()


class BoxPos:
    pos: tuple[int, int]
    zone: str = ''
    layout_mode: BoxLayoutMode = BoxLayoutMode.AUTO
    flags: BoxFlag = BoxFlag.NONE

    def __init__(self, box_pos: Optional['BoxPos']=None) -> None:
        if box_pos:
            self.eat(box_pos)
            return

        self.pos = (0, 0)
    
    def __repr__(self) -> str:
        return f"BoxPos({self.pos})"
    
    def _set_flag(self, flag: BoxFlag, yesno: bool):
        if yesno:
            self.flags |= flag
        else:
            self.flags &= ~flag
    
    def eat(self, other: 'BoxPos'):
        # faster way I found to copy a tuple without
        # linking to it.
        # write self.pos = tuple(box_pos.pos) does not
        # copy the tuple.
        self.pos = tuple(list(other.pos))
        self.zone = other.zone
        self.layout_mode = other.layout_mode
        self.flags = other.flags
    
    def is_wrapped(self) -> bool:
        return bool(self.flags & BoxFlag.WRAPPED)
    
    def is_hidden(self) -> bool:
        return bool(self.flags & BoxFlag.HIDDEN)

    def set_wrapped(self, yesno: bool):
        self._set_flag(BoxFlag.WRAPPED, yesno)
            
    def set_hidden(self, yesno: bool):
        self._set_flag(BoxFlag.HIDDEN, yesno)

    def to_point(self) -> QPoint:
        return QPoint(*self.pos)
    
    def to_pointf(self) -> QPointF:
        return QPointF(*self.pos)

    def set_pos_from_pt(self, point: Union[QPoint, QPointF]):
        self.pos = (int(point.x()), int(point.y()))

    def copy(self) -> 'BoxPos':
        return BoxPos(self)

    
# For Repulsive boxes
class Direction(IntEnum):
    NONE = 0
    LEFT = 1
    RIGHT = 2
    UP = 3
    DOWN = 4


class ConnectionThemeState(Enum):
    NORMAL = 0
    SELECTED = 1
    DISCONNECTING = 2


class GridStyle(Enum):
    NONE = 0
    TECHNICAL_GRID = 1
    GRID = 2
    CHESSBOARD = 3
    
    @classmethod
    def _missing_(cls, value) -> 'GridStyle':
        _logger.warning(
            f'Attempt to access to an invalid GridWidgetStyle: {value}')
        return GridStyle.NONE


class Zv(Enum):
    '''enum for zValue for objects directly in the scene'''
    GRID = auto()
    RUBBERBAND = auto()
    OPAC_LINE = auto() # line semi-hidden by filter
    OPAC_BOX = auto() # box semi-hidden by filter
    HIDDING_BOX = auto()
    HIDDEN_CONN = auto()
    LINE = auto()
    BOX = auto()
    NEW_BOX = auto()
    SEL_BOX_LINE = auto() # line with a selected box
    SEL_LINE = auto()
    SEL_BOX = auto()
    MOV_LINE = auto()


class ZvBox(Enum):
    '''enum for zValue for objects directly in a box'''
    PORTGRP = auto()
    PORT = auto()
    SEL_PORT = auto()
    HIDDER = auto()


class AliasingReason(Flag):
    NONE = 0x00
    USER_MOVE = auto()
    ANIMATION = auto()
    VIEW_MOVE = auto()
    SCROLL_BAR_MOVE = auto()
    NAV_ON_BORDERS = auto()


class Joining(Enum):
    NO_CHANGE = 0
    NO = 1
    YES = 2


class CanvasItemType(IntEnum):
    '''this enum is still here if really needed
    but never really used.
    Prefer use isinstance(item, type) if possible
    because IDE will know easier with which class
    we are dealing.'''
    BOX = QGraphicsItem.UserType + 1
    ICON = QGraphicsItem.UserType + 2
    PORT = QGraphicsItem.UserType + 3
    PORTGROUP = QGraphicsItem.UserType + 4
    BEZIER_LINE = QGraphicsItem.UserType + 5
    BEZIER_LINE_MOV = QGraphicsItem.UserType + 6
    HIDDEN_CONN = QGraphicsItem.UserType + 7
    RUBBERBAND = QGraphicsItem.UserType + 8


# Canvas options
class CanvasOptionsObject:
    theme_name = ""
    auto_hide_groups = True
    auto_select_items = False
    show_shadows = False
    grid_style = GridStyle.NONE
    inline_displays = 0
    elastic = True
    borders_navigation = True
    prevent_overlap = True
    max_port_width = 180
    semi_hide_opacity = 0.20
    default_zoom = 100
    box_grouped_auto_layout_ratio = 1.0
    cell_width = 16
    cell_height = 12


# Canvas features
class CanvasFeaturesObject:
    group_info = False
    group_rename = False
    port_info = True
    port_rename = False
    handle_group_pos = False


# ------------------------

# object lists            
class GroupObject:
    group_id: int
    group_name: str
    splitted: bool
    box_type: int
    icon_name: str
    box_poses: dict[PortMode, BoxPos]
    plugin_id: int
    plugin_ui: int # to verify
    plugin_inline: int # to verify
    handle_client_gui: bool
    gui_visible: bool
    widgets: list
    if TYPE_CHECKING:
        widgets: list[BoxWidget]

    def copy_no_widget(self) -> 'GroupObject':
        group_copy = GroupObject()
        group_copy.__dict__ = self.__dict__.copy()
        group_copy.widgets = []
        group_copy.box_poses = {}
        for port_mode in PortMode.in_out_both():
            group_copy.box_poses[port_mode] = \
                BoxPos(self.box_poses[port_mode])
        return group_copy


class ConnectableObject:
    group_id: int
    port_mode: PortMode
    port_type: PortType
    port_subtype: PortSubType
    portgrp_id: int
    
    def get_port_ids(self) -> tuple[int]:
        return ()


class PortObject(ConnectableObject):
    port_id: int
    port_name: str
    widget: object
    portgrp: object
    hidden_conn_widget: object
    if TYPE_CHECKING:
        widget: PortWidget
        portgrp: 'PortgrpObject'
        hidden_conn_widget: Optional[HiddenConnWidget]

    pg_pos = 0 # index in the portgroup (if any)
    pg_len = 1 # length of the portgroup (if any)

    def __repr__(self) -> str:
        return f"PortObject({self.port_name} - {self.port_id} - {self.portgrp_id})"

    def copy_no_widget(self) -> 'PortObject':
        port_copy = PortObject()
        port_copy.__dict__ = self.__dict__.copy()
        port_copy.widget = None
        port_copy.hidden_conn_widget = None
        return port_copy

    def get_port_ids(self) -> tuple[int]:
        return (self.port_id,)

    def set_portgroup_id(self, pg_id: int, pg_pos: int, pg_len: int):
        self.portgrp_id = pg_id
        self.pg_pos = pg_pos
        self.pg_len = pg_len
        if self.widget is not None:
            self.widget.set_portgroup_id(pg_id, pg_pos, pg_len)


class PortgrpObject(ConnectableObject):
    port_id_list: list[int]
    widget: object
    if TYPE_CHECKING:
        widget: Optional[PortgroupWidget]

    def __init__(self):
        self.ports = list[PortObject]()

    def copy_no_widget(self) -> 'PortgrpObject':
        portgrp_copy = PortgrpObject()
        portgrp_copy.__dict__ = self.__dict__.copy()
        portgrp_copy.widget = None
        return portgrp_copy
    
    def get_port_ids(self) -> tuple[int]:
        return tuple(self.port_id_list)


class ConnectionObject:
    connection_id: int
    group_in_id: int
    port_in_id: int
    group_out_id: int
    port_out_id: int
    port_type: PortType
    ready_to_disc: bool
    in_selected: bool
    out_selected: bool

    def copy_no_widget(self) -> 'ConnectionObject':
        conn_copy = ConnectionObject()
        conn_copy.__dict__ = self.__dict__.copy()
        return conn_copy

    def matches(self, group_id_1: int, port_ids_list_1: list[int],
                group_id_2: int, port_ids_list_2: list[int]) -> bool:
        if (self.group_in_id == group_id_1
            and self.port_in_id in port_ids_list_1
            and self.group_out_id == group_id_2
            and self.port_out_id in port_ids_list_2):
                return True
        elif (self.group_in_id == group_id_2
            and self.port_in_id in port_ids_list_2
            and self.group_out_id == group_id_1
            and self.port_out_id in port_ids_list_1):
                return True
        else:
            return False

    def concerns(self, group_id: int, port_ids_list: list[int]) -> bool:
        if (self.group_in_id == group_id
                and self.port_in_id in port_ids_list):
            return True
        elif (self.group_out_id == group_id
            and self.port_out_id in port_ids_list):
            return True
        else:
            return False

    def theme_state(self) -> ConnectionThemeState:
        if self.ready_to_disc:
            return ConnectionThemeState.DISCONNECTING
        if self.in_selected or self.out_selected:
            return ConnectionThemeState.SELECTED
        return ConnectionThemeState.NORMAL


class ClipboardElement:
    port_type: PortType
    port_mode: PortMode
    group_id: int
    port_id: int
    group_port_ids: list[int]


# Main Canvas object
class Canvas:
    def __init__(self):
        self.qobject = None
        self.settings = None
        self.theme = None

        self.initiated = False
        self.theme_paths = ()
        self.theme_manager = None

        self.group_list = list[GroupObject]()
        self.port_list = list[PortObject]()
        self.portgrp_list = list[PortgrpObject]()
        self.connection_list = list[ConnectionObject]()

        self._groups_dict = dict[int, GroupObject]()
        self._all_boxes = []
        self._ports_dict = dict[int, dict[int, PortObject]]()
        self._portgrps_dict = dict[int, dict[int, PortgrpObject]]()
        self._conns_dict = dict[int, ConnectionObject]()
        self._conns_outin_dict = dict[int, dict[int, dict[int, ConnectionObject]]]()
        self._conns_inout_dict = dict[int, dict[int, dict[int, ConnectionObject]]]()

        self.clipboard = list[ClipboardElement]()
        self.clipboard_cut = True
        self.group_plugin_map = {}

        self.scene = None
        self.initial_pos = QPointF(0, 0)
        self.size_rect = QRectF()
        self.antialiasing = True
        self.aliasing_reason = AliasingReason.NONE

        self.is_line_mov = False
        self.loading_items = False
        self.menu_shown = False
        self.menu_click_pos = QPoint(0, 0)
        
        # This is only to get object methods in IDE everywhere.
        if TYPE_CHECKING:
            self.qobject = CanvasObject()
            self.theme = Theme()
            self.theme_manager = ThemeManager()
            self.scene = PatchScene()
            self.settings = QSettings()
            self.options = CanvasOptionsObject()
            self.features = CanvasFeaturesObject()
            
            self._all_boxes = list[BoxWidget]()

    def callback(self, action: CallbackAct, value1: int,
                 value2: int, value_str: str):
        # has to be redefined in patchcanvas.init()
        pass
    
    def clear_all(self):
        self.port_list.clear()
        self._ports_dict.clear()
        self.portgrp_list.clear()
        self._ports_dict.clear()
        self.connection_list.clear()
        self._conns_dict.clear()
        self._conns_outin_dict.clear()
        self._conns_inout_dict.clear()

    def clear_all_2(self):
        self.qobject.rm_all_groups_to_join()
        self.group_list.clear()
        self._groups_dict.clear()
        self._all_boxes.clear()
        self.port_list.clear()
        self._ports_dict.clear()
        self.portgrp_list.clear()
        self._portgrps_dict.clear()
        self.connection_list.clear()
        self._conns_dict.clear()
        self._conns_outin_dict.clear()
        self._conns_inout_dict.clear()
        self.clipboard.clear()
        self.group_plugin_map.clear()
        self.scene.clear()

    def add_group(self, group: GroupObject):
        self.group_list.append(group)
        self._groups_dict[group.group_id] = group
        for widget in group.widgets:
            self._all_boxes.append(widget)

    def add_box(self, box: 'BoxWidget'):
        self._all_boxes.append(box)
        
    def remove_box(self, box: 'BoxWidget'):
        if box in self._all_boxes:
            self._all_boxes.remove(box)

    def add_port(self, port: PortObject):
        self.port_list.append(port)

        gp_dict = self._ports_dict.get(port.group_id)
        if gp_dict is None:
            self._ports_dict[port.group_id] = {port.port_id: port}
        else:
            self._ports_dict[port.group_id][port.port_id] = port
    
    def add_portgroup(self, portgrp: PortgrpObject):
        self.portgrp_list.append(portgrp)

        gp_dict = self._portgrps_dict.get(portgrp.group_id)
        if gp_dict is None:
            self._portgrps_dict[portgrp.group_id] = {portgrp.portgrp_id: portgrp}
        else:
            self._portgrps_dict[portgrp.group_id][portgrp.portgrp_id] = portgrp
        
        for port in self.list_ports(group_id=portgrp.group_id):
            if port.port_id in portgrp.port_id_list:
                portgrp.ports.append(port)
                port.portgrp = portgrp
    
    def add_connection(self, conn: ConnectionObject):
        self.connection_list.append(conn)
        self._conns_dict[conn.connection_id] = conn

        gp_outin_out_dict = self._conns_outin_dict.get(conn.group_out_id)
        gp_inout_in_dict = self._conns_inout_dict.get(conn.group_in_id)
        
        if gp_outin_out_dict is None:
            self._conns_outin_dict[conn.group_out_id] = {
                conn.group_in_id: {conn.connection_id: conn}}
        else:
            if conn.group_in_id in gp_outin_out_dict:
                gp_outin_out_dict[conn.group_in_id][conn.connection_id] = conn
            else:
                gp_outin_out_dict[conn.group_in_id] = {conn.connection_id: conn}
        
        if gp_inout_in_dict is None:
            self._conns_inout_dict[conn.group_in_id] = {
                conn.group_out_id: {conn.connection_id: conn}}
        else:
            if conn.group_out_id in gp_inout_in_dict:
                gp_inout_in_dict[conn.group_out_id][conn.connection_id] = conn
            else:
                gp_inout_in_dict[conn.group_out_id] = {conn.connection_id: conn}
    
    def remove_group(self, group: GroupObject):
        self.group_list.remove(group)
        if group.group_id in self._groups_dict.keys():
            self._groups_dict.pop(group.group_id)
        
        for widget in group.widgets:
            if widget in self._all_boxes:
                self._all_boxes.remove(widget)
                
        self.qobject.rm_group_to_join(group.group_id)
    
    def remove_port(self, port: PortObject):
        if port in self.port_list:
            self.port_list.remove(port)
        
        gp_dict = self._ports_dict.get(port.group_id)
        if gp_dict and port.port_id in gp_dict.keys():
            gp_dict.pop(port.port_id)
    
    def remove_portgroup(self, portgrp: PortgrpObject):
        if portgrp in self.portgrp_list:
            self.portgrp_list.remove(portgrp)
        
        gp_dict = self._portgrps_dict.get(portgrp.group_id)
        if gp_dict and portgrp.portgrp_id in gp_dict.keys():
            gp_dict.pop(portgrp.portgrp_id)
            
        for port in self.list_ports(group_id=portgrp.group_id):
            if port.port_id in portgrp.port_id_list:
                port.portgrp = None
    
    def remove_connection(self, conn: ConnectionObject):
        if conn in self.connection_list:
            self.connection_list.remove(conn)
            
        try:
            self._conns_dict.pop(conn.connection_id)
            self._conns_outin_dict[conn.group_out_id][conn.group_in_id].pop(
                conn.connection_id)
            self._conns_inout_dict[conn.group_in_id][conn.group_out_id].pop(
                conn.connection_id)
        except:
            pass

    def get_group(self, group_id: int) -> GroupObject:
        return self._groups_dict.get(group_id)
    
    def get_port(self, group_id: int, port_id: int) -> PortObject:
        gp = self._ports_dict.get(group_id)
        if gp is None:
            return None
        return gp.get(port_id)

    def get_portgroup(self, group_id: int, portgrp_id: int) -> PortgrpObject:
        gp = self._portgrps_dict.get(group_id)
        if gp is None:
            return None
        return gp.get(portgrp_id)

    def get_connection(self, connection_id: int) -> ConnectionObject:
        if connection_id in self._conns_dict.keys():
            return self._conns_dict[connection_id]

    def list_boxes(self) -> list['BoxWidget']:
        return self._all_boxes

    def list_ports(self, group_id: int=None) -> Iterator[PortObject]:
        if group_id is None:
            for port in self.port_list:
                yield port
            return     
        
        work_dict = self._ports_dict.get(group_id)
        if work_dict is None:
            return
        
        for port in work_dict.values():
            yield port
            
    def list_portgroups(self, group_id: int=None) -> Iterator[PortgrpObject]:
        if group_id is None:
            for portgrp in self.portgrp_list:
                yield portgrp
            return     
        
        work_dict = self._portgrps_dict.get(group_id)
        if work_dict is None:
            return
        
        for portgrp in work_dict.values():
            yield portgrp

    def list_connections(
            self, *connectables: ConnectableObject,
            group_in_id=None, group_out_id=None,
            group_id=None) -> Iterator[ConnectionObject]:
        if (not connectables
                and group_id is None
                and group_in_id is None
                and group_out_id is None):
            # no filter, list all connections
            for conn in self._conns_dict.values():
                yield conn
            return
        
        if len(connectables) > 2:
            return
        
        port_out_ids, port_in_ids = tuple[int](), tuple[int]()
        
        # check infos from connectables (port/portgroup)
        if len(connectables) == 2:
            if (connectables[0].port_mode
                    is not connectables[1].port_mode.opposite()):
                return
            
            if connectables[0].port_mode is PortMode.OUTPUT:
                connectable_out, connectable_in = connectables
            else:
                connectable_in, connectable_out = connectables
            
            group_out_id = connectable_out.group_id
            group_in_id = connectable_in.group_id
            port_out_ids = connectable_out.get_port_ids()
            port_in_ids = connectable_in.get_port_ids()

        elif len(connectables) == 1:
            if connectables[0].port_mode is PortMode.OUTPUT:
                group_out_id = connectables[0].group_id
                port_out_ids = connectables[0].get_port_ids()
            else:
                group_in_id = connectables[0].group_id
                port_in_ids = connectables[0].get_port_ids()

        # check if group_id should be group_out_id or group_in_id
        if (group_id is not None
                and (group_out_id is not None or group_in_id is not None)):
            if group_out_id is None:
                group_out_id = group_id
            elif group_in_id is None:
                group_in_id = group_id
            group_id = None

        # no precision for group_id
        # we check first in the out dict, then in the in dict
        if group_id is not None:
            gp_out = self._conns_outin_dict.get(group_id)
            if gp_out is not None:
                for gp_out_in in gp_out.values():
                    for conn in gp_out_in.values():
                        yield conn
        
            gp_in = self._conns_inout_dict.get(group_id)
            if gp_in is not None:
                for gp_id, gp_in_out in gp_in.items():
                    if gp_id == group_id:
                        # connections here have already been yielded
                        continue
                    for conn in gp_in_out.values():
                        yield conn
            return
        
        # here we are sure we have group_out_id or group_in_id filter(s)
        if group_out_id is not None:
            gp_out = self._conns_outin_dict.get(group_out_id)
            if gp_out is None:
                return
            
            if group_in_id is not None:
                gp_in = gp_out.get(group_in_id)
                if gp_in is None:
                    return
                
                for conn in gp_in.values():
                    if ((not port_out_ids or conn.port_out_id in port_out_ids)
                            and (not port_in_ids or conn.port_in_id in port_in_ids)):
                        yield conn
                return
            
            for gp_in in gp_out.values():
                for conn in gp_in.values():
                    if not port_out_ids or conn.port_out_id in port_out_ids:
                        yield conn
            return

        # here we are sure we have no group_out_id filter
        gp_in = self._conns_inout_dict.get(group_in_id)
        if gp_in is None:
            return
        
        for gp_out in gp_in.values():
            for conn in gp_out.values():
                if not port_in_ids or conn.port_in_id in port_in_ids:
                    yield conn

    def set_aliasing_reason(
            self, aliasing_reason: AliasingReason, yesno: bool):
        is_aliasing = bool(self.aliasing_reason)
        
        if yesno:
            self.aliasing_reason |= aliasing_reason
        else:
            self.aliasing_reason &= ~aliasing_reason
        
        if bool(self.aliasing_reason) is is_aliasing:
            return
        
        if self.scene is not None:
            self.scene.set_anti_aliasing(not bool(self.aliasing_reason))

# -----------------------------

# Global objects
canvas = Canvas()

options = CanvasOptionsObject()
features = CanvasFeaturesObject()
