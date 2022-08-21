
from typing import TYPE_CHECKING
from PyQt5.QtGui import QIcon, QPalette, QColor, QKeySequence
from PyQt5.QtWidgets import QFrame
from PyQt5.QtCore import pyqtSlot, pyqtSignal

from .base_elements import TransportPosition, TransportViewMode
from .ui.transport_controls import Ui_FrameTransportControls

if TYPE_CHECKING:
    from .patchbay_manager import PatchbayManager


class TransportControlsFrame(QFrame):
    backwards = pyqtSignal()
    forwards = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_FrameTransportControls()
        self.ui.setupUi(self)
        
        self.ui.toolButtonPlayPause.clicked.connect(self._play_clicked)
        self.ui.toolButtonStop.clicked.connect(self._stop_clicked)
        self.ui.toolButtonRewind.clicked.connect(self._rewind_clicked)
        self.ui.toolButtonForward.clicked.connect(self._forward_clicked)
        self.ui.labelTime.transport_view_changed.connect(self._transport_view_changed)
        
        self._patchbay_mng: 'PatchbayManager' = None
        self._samplerate = 48000
        self._last_transport_pos = TransportPosition(0, False, False, 0, 0, 0, 120.00)
        
        # self._play_pause_action = QAction()
        # self._play_pause_action.triggered.connect(self._play_clicked)
        # self.ui.toolButtonPlayPause.setDefaultAction(self._play_pause_action)
        self.ui.toolButtonPlayPause.setShortcut(QKeySequence(' '))
        
        # set theme
        app_bg = self.ui.labelTempo.palette().brush(
            QPalette.Active, QPalette.Background).color()
        dark = bool(app_bg.lightness() <= 128)
        
        scheme = 'dark' if dark else 'light'
        self._icon_play = QIcon(f':/transport/{scheme}/media-playback-start.svg')
        self._icon_pause = QIcon(f':/transport/{scheme}/media-playback-pause.svg')
        
        self.ui.toolButtonRewind.setIcon(
            QIcon(f':/transport/{scheme}/media-seek-backward.svg'))
        self.ui.toolButtonForward.setIcon(
            QIcon(f':/transport/{scheme}/media-seek-forward.svg'))
        self.ui.toolButtonPlayPause.setIcon(self._icon_play)
        # self._play_pause_action.setIcon(self._icon_play)
        self.ui.toolButtonStop.setIcon(
            QIcon(f':/transport/{scheme}/media-playback-stop.svg'))

        bg = QColor(app_bg)
        more_gray = 20 if dark else -30
        
        bg.setRed(max(min(app_bg.red() + more_gray, 255), 0))
        bg.setGreen(max(min(app_bg.green() + more_gray, 255), 0))
        bg.setBlue(max(min(app_bg.blue() + more_gray, 255), 0))
        background = bg.name()

        round_side = 'left'
        for button in (self.ui.toolButtonRewind, self.ui.toolButtonPlayPause,
                       self.ui.toolButtonForward, self.ui.toolButtonStop):
            if button is self.ui.toolButtonForward:
                round_side = "right"
            
            button.setStyleSheet(f"QToolButton{{background:{background}; border:none;"
                                 f"border-top-{round_side}-radius:4px;"
                                 f"border-bottom-{round_side}-radius:4px}}")
        
        count_bg = '#222' if dark else '#eee'
        count_bg = self.palette().base().color().name()
        
        self.ui.labelTime.setStyleSheet(
            f"QLabel{{background:{count_bg}; border: 2px solid {background}}}")
            
    def _play_clicked(self, play: bool):
        if self._patchbay_mng is not None:
            self._patchbay_mng.transport_play_pause(play)
            
    def _stop_clicked(self):
        if self._patchbay_mng is not None:
            self._patchbay_mng.transport_stop()
    
    def _rewind_clicked(self):
        if self._patchbay_mng is not None:
            self._patchbay_mng.transport_relocate(
                max(int(self._last_transport_pos.frame - 2.5 * self._samplerate), 0))
        
    def _forward_clicked(self):
        if self._patchbay_mng is not None:
            self._patchbay_mng.transport_relocate(
                int(self._last_transport_pos.frame + 2.5 * self._samplerate))
    
    def set_patchbay_manager(self, mng: 'PatchbayManager'):
        self._patchbay_mng = mng
    
    def set_samplerate(self, samplerate: int):
        self._samplerate = samplerate
    
    def refresh_transport(self, transport_pos: TransportPosition):
        self.ui.toolButtonPlayPause.setChecked(transport_pos.rolling)
        if transport_pos.rolling:
            self.ui.toolButtonPlayPause.setIcon(self._icon_pause)
            # self._play_pause_action.setIcon(self._icon_pause)
        else:
            self.ui.toolButtonPlayPause.setIcon(self._icon_play)
            # self._play_pause_action.setIcon(self._icon_play)
            
        if self.ui.labelTime.transport_view_mode is not TransportViewMode.FRAMES:
            # switch the view mode in case beats info appears/disappears 
            if transport_pos.valid_bbt and not self._last_transport_pos.valid_bbt:
                self.ui.labelTime.transport_view_mode = TransportViewMode.BEAT_BAR_TICK
            elif not transport_pos.valid_bbt and self._last_transport_pos.valid_bbt:
                self.ui.labelTime.transport_view_mode = TransportViewMode.HOURS_MINUTES_SECONDS
        
        if (self.ui.labelTime.transport_view_mode
                is TransportViewMode.HOURS_MINUTES_SECONDS):
            time = transport_pos.frame // self._samplerate
            secs = time % 60
            mins = (time / 60) % 60
            hrs  = (time / 3600) % 60
            self.ui.labelTime.setText("%02i:%02i:%02i" % (hrs, mins, secs))
            
        elif (self.ui.labelTime.transport_view_mode
                is TransportViewMode.FRAMES):
            frame1 =  transport_pos.frame % 1000
            frame2 = int(transport_pos.frame / 1000) % 1000
            frame3 = int(transport_pos.frame / 1000000) % 1000
            
            self.ui.labelTime.setText("%03i'%03i'%03i" % (frame3, frame2, frame1))
            
        elif (self.ui.labelTime.transport_view_mode
                is TransportViewMode.BEAT_BAR_TICK):
            if transport_pos.valid_bbt:
                self.ui.labelTime.setText(
                    "%03i|%02i|%04i" % (transport_pos.bar,
                                        transport_pos.beat,
                                        transport_pos.tick))
            else:
                self.ui.labelTime.setText("000|00|0000")
                
        if transport_pos.valid_bbt:
            if int(transport_pos.beats_per_minutes) == transport_pos.beats_per_minutes:
                self.ui.labelTempo.setText(f"{int(transport_pos.beats_per_minutes)} BPM")
            else:
                self.ui.labelTempo.setText('%.2f BPM' % transport_pos.beats_per_minutes)
        else:
            self.ui.labelTempo.setText('')
            
        self.ui.toolButtonRewind.setEnabled(transport_pos.frame != 0)

        self._last_transport_pos = transport_pos
            
    
    @pyqtSlot()
    def _transport_view_changed(self):
        self.refresh_transport(self._last_transport_pos)