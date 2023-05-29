# -*- coding: utf-8 -*-
# This file is part of AYAB.
#
#    AYAB is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    AYAB is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with AYAB.  If not, see <http://www.gnu.org/licenses/>.
#
#    Copyright 2013 Christian Obersteiner, Andreas Müller, Christian Gerbrandt
#    https://github.com/AllYarnsAreBeautiful/ayab-desktop
"""
Mock Class of Communication for Test/Simulation purposes
"""

import logging
from time import sleep
from collections import deque

from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QMessageBox

from .communication import Communication, Token


class CommunicationMock(Communication):
    """Class Handling the mock communication protocol."""
    def __init__(self, delay=True, step=False) -> None:
        """Initialize communication."""
        logging.basicConfig(level=logging.DEBUG)
        self.logger = logging.getLogger(type(self).__name__)
        self.__delay = delay
        self.__step = step
        self.reset()

    def __del__(self) -> None:
        """Handle behaviour on deletion."""
        pass

    def reset(self):
        self.__is_open = False
        self.__is_started = False
        self.rx_msg_list = deque([], maxlen=100)
        self.__line_count = 0

    def is_open(self) -> bool:
        """Return status of the interface."""
        return self.__is_open

    def close_serial(self) -> None:
        """Close communication."""
        self.reset()

    def open_serial(self, portname=None) -> bool:
        """Open communication."""
        self.__is_open = True
        # if self.__delay:
        #     sleep(2) # wait for knitting progress dialog
        return True

    def req_info(self) -> None:
        """Send a request for API version information."""
        cnfInfo = bytes([Token.cnfInfo.value, 6, 1, 0])  # APIv6, FWv1.0
        self.rx_msg_list.append(cnfInfo)

    def req_init_API6(self, machine_val):
        """Send machine type."""
        cnfInit = bytes([Token.cnfInit.value, 0])
        self.rx_msg_list.append(cnfInit)
        indState = bytes(
            [Token.indState.value, 0, 1, 0xFF, 0xFF, 0xFF, 0xFF, 1, 0x00, 1])
        self.rx_msg_list.append(indState)

    def req_test_API6(self) -> None:
        """Send a request for hardware testing."""
        cnfTest = bytes([Token.cnfTest.value, 0])
        self.rx_msg_list.append(cnfTest)

    def req_start_API6(self, start_needle, stop_needle,
                       continuous_reporting) -> None:
        """Send a request to start knitting."""
        self.__is_started = True
        cnfStart = bytes([Token.cnfStart.value, 0])
        self.rx_msg_list.append(cnfStart)

    def cnf_line_API6(self, line_number, color, flags, line_data) -> bool:
        """Send a row of stitch data."""
        return True

    def update_API6(self) -> tuple:
        """Read and parse data packet."""
        if self.__is_open and self.__is_started:
            reqLine = bytes([Token.reqLine.value, self.__line_count])
            self.__line_count += 1
            self.__line_count %= 256
            self.rx_msg_list.append(reqLine)
            if self.__delay:
                sleep(1)  # wait for knitting progress dialog to update
            # step through output line by line
            if self.__step:
                # pop up box waits for user input before moving on to next line
                msg = QMessageBox()
                msg.setIcon(QMessageBox.Information)
                msg.setText("Line number = " + str(self.__line_count))
                msg.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
                ret = None
                ret = msg.exec_()
                while ret == None:
                    pass
        if len(self.rx_msg_list) > 0:
            return self.parse_API6(self.rx_msg_list.popleft())  # FIFO
        # else
        return self.parse_API6(None)
