from enum import IntEnum
import logging
from typing import Callable

from .init_values import PortMode, GroupObject, canvas, BoxType
from .box_widget import BoxWidget

_logger = logging.getLogger(__name__)

class GoTo(IntEnum):
    NONE = 0
    LEFT = 1
    RIGHT = 2


class BoxAlign(IntEnum):
    LEFT = 0
    CENTER = 1
    RIGHT = 2


class BoxArranger:
    group_id: int
    hardware: bool
    port_mode: PortMode
    conns_in_group_ids: set[int]
    conns_out_group_ids: set[int]
    box: BoxWidget

    def __init__(self, arranger: 'CanvasArranger',
                 group: GroupObject, port_mode: PortMode):
        self.arranger = arranger
        self.box: BoxWidget = None
        
        # we don't take the group here
        # because it can be splitted during the BoxArranger life
        self.group_id = group.group_id
        self.box_type = group.box_type
        self.group_name = group.group_name
        self.port_mode = port_mode

        self.conns_in_group_ids = set[int]()
        self.conns_out_group_ids = set[int]()
        self.col_left = 2 # is mininum if not fixed
        self.col_right = -2 # is maximum if not fixed
        self.col_left_fixed = False
        self.col_right_fixed = False
        self.col_left_counted = False
        self.col_right_counted = False
        self.analyzed = False
        
        self.ins_connected_to = list[BoxArranger]()
        self.outs_connected_to = list[BoxArranger]()
        
        self.y_pos = 0.0
        self.column = 0

    def __repr__(self) -> str:
        return f"BoxArranger({self.group_name}, {self.port_mode.name})"
    
    def __lt__(self, other: 'BoxArranger') -> bool:
        if self.box_type is not other.box_type:
            if self.box_type is BoxType.APPLICATION:
                return False
            if other.box_type is BoxType.APPLICATION:
                return True
            
            return self.box_type < other.box_type
        
        return self.group_id < other.group_id
    
    def set_box(self):
        group = canvas.get_group(self.group_id)
        if self.port_mode in (PortMode.OUTPUT, PortMode.BOTH):
            self.box = group.widgets[0]
        else:
            self.box = group.widgets[1]
            
        if self.box is None:
            _logger.error(f"{self} did not found its box !")
    
    def is_owner(self, group_id: int, port_mode: PortMode):
        return bool(self.group_id == group_id
                    and self.port_mode & port_mode)
    
    def set_next_boxes(self, box_arrangers: list['BoxArranger']):
        for group_id in self.conns_in_group_ids:
            for box_arranger in box_arrangers:
                if box_arranger.is_owner(group_id, PortMode.INPUT):
                    self.outs_connected_to.append(box_arranger)
                    break

        for group_id in self.conns_out_group_ids:
            for box_arranger in box_arrangers:
                if box_arranger.is_owner(group_id, PortMode.OUTPUT):
                    self.ins_connected_to.append(box_arranger)
                    break
        
        # self.outs_connected_to.sort()
        # self.ins_connected_to.sort()
    
    def parse_all(self, path: list['BoxArranger']=[]):
        if self.arranger.ba_to_split is not None:
            return
        
        if self in path:
            return
        
        path.append(self)
        
        self.count_left()
        if self.arranger.ba_to_split:
            return

        self.count_right()
        if self.arranger.ba_to_split:
            return
        
        for ba_in in self.ins_connected_to:
            ba_in.parse_all(path)
        
        for ba_out in self.outs_connected_to:
            ba_out.parse_all(path)
            
        self.analyzed = True
    
    def count_left(self, path: list['BoxArranger']=[]):
        if self.arranger.ba_to_split is not None:
            return
        
        if self.col_left_fixed or self.col_left_counted:
            return
        
        if self in path:
            self.arranger.ba_to_split = self
            return
        
        path = path.copy()
        path.append(self)
        
        for ba in self.ins_connected_to:
            ba.count_left(path)
        
        left_min = self.col_left
        fixed = 0

        for ba in self.ins_connected_to:
            left_min = max(left_min, ba.col_left + 1)
            if ba.col_left_fixed:
                fixed += 1

        self.col_left = left_min
        if fixed and fixed == len(self.ins_connected_to):
            self.col_left_fixed = True
        
        self.col_left_counted = True
    
    def count_right(self, path: list['BoxArranger']=[]):
        if self.arranger.ba_to_split is not None:
            return
        
        if self.col_right_fixed or self.col_right_counted:
            return
        
        if self in path:
            self.arranger.ba_to_split = self
            return
        
        path = path.copy()
        path.append(self)
        
        for ba in self.outs_connected_to:
            ba.count_right(path)

        right_min = self.col_right
        fixed = 0
        
        for ba in self.outs_connected_to:
            right_min = min(right_min, ba.col_right - 1)
            if ba.col_right_fixed:
                fixed += 1
        
        self.col_right = right_min
        if fixed and fixed == len(self.outs_connected_to):
            self.col_right_fixed = True

        self.col_right_counted = True
    
    def get_needed_columns(self) -> int:
        return self.col_left - self.col_right - 1
    
    def get_level(self, n_columns: int) -> int:
        if self.col_left_fixed:
            return self.col_left
        
        if self.col_right_fixed:
            return n_columns + self.col_right + 1
        
        return self.col_left

    def get_box_align(self) -> BoxAlign:
        if self.port_mode is PortMode.OUTPUT:
            return BoxAlign.RIGHT
        if self.port_mode is PortMode.INPUT:
            return BoxAlign.LEFT
        if self.outs_connected_to and self.ins_connected_to:
            return BoxAlign.CENTER
        if self.outs_connected_to:
            return BoxAlign.RIGHT
        if self.ins_connected_to:
            return BoxAlign.LEFT
        return BoxAlign.CENTER

    def reset(self):
        self.col_left = 2
        self.col_left_counted = False
        self.col_left_fixed = False
        self.col_right = -2
        self.col_right_counted = False
        self.col_right_fixed = False
        self.analyzed = False


class CanvasArranger:
    def __init__(self, join_group: Callable[[int], None],
                 split_group: Callable[[int], None]):
        self.box_arrangers = list[BoxArranger]()
        self.ba_networks = list[list[BoxArranger]]()

        # is set only in case there are looping connections
        # around this box arranger.
        self.ba_to_split: BoxArranger = None

        self.join_group = join_group
        self.split_group = split_group

        to_split_group_ids = set[int]()

        for conn in canvas.list_connections():
            if conn.group_out_id == conn.group_in_id:
                to_split_group_ids.add(conn.group_out_id)

        for group in canvas.group_list:
            if (group.box_type is BoxType.HARDWARE
                    or group.group_id in to_split_group_ids):
                self.box_arrangers.append(
                    BoxArranger(self, group, PortMode.OUTPUT))
                self.box_arrangers.append(
                    BoxArranger(self, group, PortMode.INPUT))
            else:
                self.box_arrangers.append(
                    BoxArranger(self, group, PortMode.BOTH))

        for conn in canvas.list_connections():
            for box_arranger in self.box_arrangers:
                if box_arranger.is_owner(conn.group_out_id, PortMode.OUTPUT):
                    box_arranger.conns_in_group_ids.add(conn.group_in_id)
                if box_arranger.is_owner(conn.group_in_id, PortMode.INPUT):
                    box_arranger.conns_out_group_ids.add(conn.group_out_id)
    
        for box_arranger in self.box_arrangers:
            box_arranger.set_next_boxes(self.box_arrangers)

    def needs_to_split_a_box(self) -> bool:
        if self.ba_to_split is None:
            return False

        group = canvas.get_group(self.ba_to_split.group_id)
        new_ba = BoxArranger(self, group, PortMode.INPUT)
        new_ba.ins_connected_to = self.ba_to_split.ins_connected_to
        
        for ba in self.ba_to_split.ins_connected_to:
            ba.outs_connected_to.remove(self.ba_to_split)
            ba.outs_connected_to.append(new_ba)

        self.ba_to_split.ins_connected_to = []
        self.ba_to_split.port_mode = PortMode.OUTPUT
        
        self.box_arrangers.append(new_ba)
        self.ba_to_split = None

        for ba in self.box_arrangers:
            ba.reset()

        return True

    def set_all_levels(self) -> bool:
        self.ba_to_split = None
        self.ba_networks.clear()
        
        print('____==CUSTOM')
        for box_arranger in self.box_arrangers:
            if (box_arranger.col_left == 1
                    and box_arranger.col_left_fixed
                    and not box_arranger.analyzed):
                ba_network = list[BoxArranger]()
                box_arranger.parse_all(ba_network)

                if self.needs_to_split_a_box():
                    return False

                self.ba_networks.append(ba_network)
        
        for box_arranger in self.box_arrangers:
            if (box_arranger.col_right == -1
                    and box_arranger.col_right_fixed
                    and not box_arranger.analyzed):
                ba_network = list[BoxArranger]()
                box_arranger.parse_all(ba_network)
                
                if self.needs_to_split_a_box():
                    return False
                
                self.ba_networks.append(ba_network)

        for box_arranger in self.box_arrangers:
            if box_arranger.analyzed:
                continue
            
            ba_network = list[BoxArranger]()
            box_arranger.parse_all(ba_network)
            
            if self.needs_to_split_a_box():
                return False
            
            self.ba_networks.append(ba_network)
            
        n_columns = 3
        for ba in self.box_arrangers:
            n_columns = max(n_columns, ba.get_needed_columns())
        
        for ba in self.box_arrangers:
            if ba.get_needed_columns() == n_columns:
                ba.col_left_fixed = True
                ba.col_right_fixed = True

        for ba_network in self.ba_networks:
            while True:
                for ba in ba_network:
                    ba.col_left_counted = False
                    ba.col_right_counted = False
                    ba.analyzed = False
                    
                    if not (ba.col_left_fixed or ba.col_right_fixed):
                        ba.count_left()
                        ba.count_right()
                        if ba.col_left_fixed or ba.col_right_fixed:
                            break
                else:
                    break
        
        return True
    
    def get_group_ids_to_split(self) -> set[int]:
        group_ids = set[int]()
        
        for ba in self.box_arrangers:
            if ba.port_mode is not PortMode.BOTH:
                group_ids.add(ba.group_id)
        
        return group_ids
    
    def end_of_script(self):
        print('début du script')

        correct_leveling = False
        while not correct_leveling:
            for box_arranger in self.box_arrangers:
                box_arranger.reset()
                
                if box_arranger.box_type is BoxType.HARDWARE:
                    if box_arranger.port_mode & PortMode.OUTPUT:
                        box_arranger.col_left = 1
                        box_arranger.col_left_fixed = True
                    else:
                        box_arranger.col_right = -1
                        box_arranger.col_right_fixed = True
            correct_leveling = self.set_all_levels()
        
        group_ids_to_split = self.get_group_ids_to_split()

        # join or split groups we want to join or split
        while True:
            for group in canvas.group_list:
                if group.split:
                    if (group.box_type is not BoxType.HARDWARE
                            and group.group_id not in group_ids_to_split):
                        self.join_group(group.group_id)
                        break
                else:
                    if (group.box_type is BoxType.HARDWARE
                            or group.group_id in group_ids_to_split):
                        self.split_group(group.group_id)
                        break
            else:
                break
        
        for box_arranger in self.box_arrangers:
            box_arranger.set_box()

        number_of_columns = max(
            [ba.get_needed_columns() for ba in self.box_arrangers] + [3])

        column_widths = dict[int, float]()
        columns_pos = dict[int, float]()
        columns_bottoms = dict[int, float]()
        last_pos = 0

        for column in range(1, number_of_columns + 1):
            columns_bottoms[column] = 0.0

        last_top, last_bottom = 0.0, 0.0
        direction = GoTo.NONE
        previous_column = 0

        for ba_network in self.ba_networks:
            if len(ba_network) <= 1:
                continue

            for ba in ba_network:            
                column = ba.get_level(number_of_columns)
                
                if direction is GoTo.NONE:
                    if column > previous_column:
                        direction = GoTo.RIGHT
                    elif column < previous_column:
                        direction = GoTo.LEFT
                
                if column in (1, number_of_columns):
                    y_pos = columns_bottoms[column]

                elif ((direction is GoTo.RIGHT and column > previous_column)
                        or (direction == GoTo.LEFT and column < previous_column)):
                    y_pos = last_top
                else:
                    y_pos = last_bottom
                    last_bottom = 0.0
                    direction = GoTo.NONE

                ba.column = column
                ba.y_pos = y_pos

                if column not in (1, number_of_columns):
                    last_top = y_pos
                
                bottom = (y_pos
                        + ba.box.boundingRect().height()
                        + canvas.theme.box_spacing)
                
                columns_bottoms[column] = bottom
                if column not in (1, number_of_columns):
                    last_bottom = max(bottom, last_bottom)

                previous_column = column

        for ba_network in self.ba_networks:
            if len(ba_network) != 1:
                continue

            ba = ba_network[0]
            
            if ba.get_level(number_of_columns) in (1, number_of_columns):
                ba.column = ba.get_level(number_of_columns)
                ba.y_pos = columns_bottoms[ba.column]
                columns_bottoms[ba.column] += (ba.box.boundingRect().height()
                                               + canvas.theme.box_spacing)
                continue
            
            # This is an isolated box (without connections)
            # we place it in the column with the lowest bottom value,
            # (the nearest from top)
            choosed_column = 2            
            bottom_min = min([columns_bottoms[c] for c in columns_bottoms
                              if c not in (1, number_of_columns)])
            
            for column, bottom in columns_bottoms.items():
                if column in (1, number_of_columns):
                    continue

                if bottom == bottom_min:
                    choosed_column = column
                    break
            
            ba.column = choosed_column
            ba.y_pos = bottom_min

            columns_bottoms[ba.column] += (ba.box.boundingRect().height()
                                                + canvas.theme.box_spacing)

        max_hardware = 0
        max_middle = 0

        for column in range(1, number_of_columns + 1):
            column_widths[column] = 0.0

        for ba in self.box_arrangers:
            column_width = column_widths.get(ba.column)
            if column_width is None:
                print('OHOH', ba, ba.get_level(number_of_columns), number_of_columns)
                column_width = 0.0
            column_widths[ba.column] = max(
                ba.box.boundingRect().width(), column_width)

        for column in range(1, number_of_columns + 1):
            columns_pos[column] = last_pos
            
            last_pos += column_widths[column] + 80

        for column, bottom in columns_bottoms.items():
            if column in (1, number_of_columns):
                max_hardware = max(max_hardware, bottom)
            else:
                max_middle = max(max_middle, bottom)

        for ba in self.box_arrangers:
            if ba.column in (1, number_of_columns):
                y_offset = (columns_bottoms[ba.column] - max_hardware) / 2
            else:
                y_offset = (max_hardware - max_middle) / 2

            if ba.get_box_align() is BoxAlign.CENTER:
                x_pos = (columns_pos[ba.column]
                         + (column_widths[ba.column]
                            - ba.box.boundingRect().width()) / 2)
            elif ba.get_box_align() is BoxAlign.RIGHT:
                x_pos = (columns_pos[ba.column]
                         + column_widths[ba.column]
                         - ba.box.boundingRect().width())
            else:
                x_pos = columns_pos[ba.column] 

            canvas.scene.add_box_to_animation(
                ba.box, int(x_pos), int(ba.y_pos + y_offset))