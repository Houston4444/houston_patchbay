
from typing import TYPE_CHECKING, Iterator

from PyQt5.QtCore import pyqtSlot, QTimer, QPoint
from PyQt5.QtGui import QIcon, QPixmap, QMouseEvent
from PyQt5.QtWidgets import QToolButton, QMenu, QApplication, QAction

from .base_elements import PortMode
from .base_group import Group
from .patchcanvas import utils

if TYPE_CHECKING:
    from .patchbay_manager import PatchbayManager


_translate = QApplication.translate


class HiddensIndicator(QToolButton):
    def __init__(self, parent):
        super().__init__(parent)
        
        self.mng: 'PatchbayManager' = None
        
        self._count = 0
        self._is_blinking = False
        self._blink_timer = QTimer()
        self._blink_timer.setInterval(400)
        self._blink_timer.timeout.connect(self._blink_timer_timeout)
        
        self._BLINK_TIMES = 6
        self._blink_times_done = 0
        
        dark = '-dark' if self._is_dark() else ''

        self._icon_normal = QIcon(QPixmap(f':scalable/breeze{dark}/hint.svg'))
        self._icon_orange = QIcon(QPixmap(f':scalable/breeze{dark}/hint_orange.svg'))
        
        self.setIcon(self._icon_normal)
        self._menu = QMenu()

    def _is_dark(self) -> bool:
        return self.palette().text().color().lightnessF() > 0.5

    def set_patchbay_manager(self, mng: 'PatchbayManager'):
        self.mng = mng
        self.mng.sg.view_changed.connect(self._view_changed)
        self.mng.sg.port_types_view_changed.connect(
            self._port_types_view_changed)
        self.mng.sg.hidden_boxes_changed.connect(
            self._hidden_boxes_changed)
        self.mng.sg.group_added.connect(self._group_added)
        self.mng.sg.group_removed.connect(self._group_removed)
        self.mng.sg.all_groups_removed.connect(self._all_groups_removed)
        
    def set_count(self, count: int):
        self._count = count
        self.setText(str(count))
        
    def add_one(self):
        self._count += 1
        self.setText(str(self._count))
        self._start_blink()
    
    def _start_blink(self):
        if self._blink_timer.isActive():
            return
        
        self.setIcon(self._icon_orange)
        self._blink_times_done = 1
        self._blink_timer.start()
    
    def _stop_blink(self):
        self._blink_timer.stop()
        self.setIcon(self._icon_normal)
    
    def _check_count(self):
        cg = 0
        for group in self._list_hidden_groups():
            cg += 1

        pv_count = self._count
        self.set_count(cg)
        if cg:
            if cg > pv_count:
                self._start_blink()
        else:
            self._stop_blink()
    
    @pyqtSlot()
    def _blink_timer_timeout(self):
        self._blink_times_done += 1
        if self._blink_times_done % 2:
            self.setIcon(self._icon_orange)
        else:
            self.setIcon(self._icon_normal)
        
        if self._blink_times_done == self._BLINK_TIMES:
            self._blink_times_done = 0
            self._blink_timer.stop()
    
    @pyqtSlot(int)
    def _view_changed(self, view_num: int):
        self._check_count()
        
    @pyqtSlot(int)
    def _port_types_view_changed(self, port_types_flag: int):
        self._check_count()
    
    @pyqtSlot()
    def _hidden_boxes_changed(self):
        self._check_count()
    
    @pyqtSlot(int)
    def _group_added(self, group_id: int):
        group = self.mng.get_group_from_id(group_id)
        if group is None:
            return

        if group.current_position.hidden_port_modes() is PortMode.NULL:
            return

        if group.is_in_port_types_view(self.mng.port_types_view):
            self.add_one()

    @pyqtSlot(int)
    def _group_removed(self, group_id: int):
        self._check_count()
        
    @pyqtSlot()
    def _all_groups_removed(self):
        self.set_count(0)
        self._stop_blink()
    
    def _list_hidden_groups(self) -> Iterator[Group]:
        if self.mng is None:
            return
        
        for group in self.mng.groups:
            hpm = group.current_position.hidden_port_modes()
            if hpm is PortMode.NULL:
                continue
            
            if ((group.outs_ptv & self.mng.port_types_view
                        and PortMode.OUTPUT in hpm)
                    or (group.ins_ptv & self.mng.port_types_view
                        and PortMode.INPUT in hpm)):
                yield group
    
    def mousePressEvent(self, event: QMouseEvent) -> None:
        super().mousePressEvent(event)
        if self.mng is None:
            return        
        
        self._menu.clear()
        
        dark = self._is_dark()
        cg = 0
        
        for group in self._list_hidden_groups():
            cg += 1

            group_act = self._menu.addAction(group.cnv_name)
            group_act.setIcon(utils.get_icon(
                group.cnv_box_type, group.cnv_icon_name,
                group.current_position.hidden_port_modes(),
                dark=dark))
            group_act.setData(group.group_id)
        
        self.set_count(cg)

        WHITE_LIST = -2
        SHOW_ALL = -3
        HIDE_ALL = -4

        self._menu.addSeparator()

        is_white_list = False
        view_data = self.mng.views_datas.get(self.mng.view_number)
        if view_data is not None:
            is_white_list = view_data.is_white_list

        white_list_act = QAction(self._menu)
        white_list_act.setText(
            _translate('hiddens_indicator', 'Hide all new boxes'))
        white_list_act.setData(WHITE_LIST)
        white_list_act.setCheckable(True)
        white_list_act.setChecked(is_white_list)
        white_list_act.setIcon(QIcon.fromTheme('color-picker-white'))
        
        self._menu.addAction(white_list_act)

        self._menu.addSeparator()
        
        show_all_act = QAction(self._menu)
        show_all_act.setText(
            _translate('hiddens_indicator', 'Display all boxes'))
        show_all_act.setIcon(QIcon.fromTheme('visibility'))
        show_all_act.setData(SHOW_ALL)
        self._menu.addAction(show_all_act)
        
        hide_all_act = QAction(self._menu)
        hide_all_act.setText(
            _translate('hiddens_indicator', 'Hide all boxes'))
        hide_all_act.setIcon(QIcon.fromTheme('hint'))
        hide_all_act.setData(HIDE_ALL)
        self._menu.addAction(hide_all_act)

        sel_act = self._menu.exec(
            self.mapToGlobal(QPoint(0, self.height())))
        
        if sel_act is None:
            return
        
        act_data: int = sel_act.data()

        if act_data == WHITE_LIST:
            if white_list_act.isChecked():
                self.mng.clear_absents_in_view()
            self.mng.views_datas[self.mng.view_number].is_white_list = \
                white_list_act.isChecked()
            return
        
        if act_data == SHOW_ALL:
            self.mng.restore_all_group_hidden_sides(even_absents=is_white_list)
            return
        
        if act_data == HIDE_ALL:
            self.mng.hide_all_groups()
            return

        # act_data is now a group_id
        self.mng.restore_group_hidden_sides(act_data)
        
        