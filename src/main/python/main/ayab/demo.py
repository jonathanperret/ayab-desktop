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
#    https://github.com/AllYarnsAreBeautiful/ayab-desktop
"""Scripted walkthrough of the app, used to record demo videos in CI.

Enabled by setting the `AYAB_DEMO` environment variable. The script opens
and closes the various dialogs, runs a hardware test and exercises the
image transforms using the Simulation port, then starts knitting a bundled
pattern in Heart of Pluto mode and a lace pattern in single bed mode,
canceling each after a few rows. Finally, it switches the language to French
and quits, asking to be relaunched (see utils/record_demo.py), and then quits
again. The process exit code is 0 if everything went as expected, non-zero
otherwise; the result is also written to `AYAB_DEMO_RESULT` if set.

Optional environment variables:
- `AYAB_DEMO_PATTERN`: pattern file to load (default: a bundled pattern)
- `AYAB_DEMO_TIMEOUT`: seconds before giving up (default: 300)
- `AYAB_DEMO_RESULT`: file to write "success" or "failure" to when done
  (useful when the exit code is not propagated, e.g. under `fbs run`), or
  "relaunch" followed by the language to restore, on a second line
- `AYAB_DEMO_RELAUNCH`: set when relaunched, to the language to restore
- `AYAB_DEMO_STEPS`: file to append each step to, as a JSON line with its
  wall-clock time (used by utils/record_demo.py to caption the video and
  add chapters)
- `AYAB_DEMO_MENU_DIR`: directory through which native (macOS) menus are
  shown by utils/record_demo.py, since Qt cannot open them itself
"""

from __future__ import annotations
import json
import logging
import os
import time
from os.path import basename
from typing import TYPE_CHECKING, Callable, Generator, TypeVar

from PySide6.QtCore import QCoreApplication, QLocale, QObject, QTimer
from PySide6.QtGui import QAction, QGuiApplication
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QInputDialog,
    QMenu,
    QMessageBox,
    QWidget,
)

from .engine.engine_fsm import Operation
from .engine.mode import Mode
from .preferences import PrefsLangWidget
from .engine.output import Output

if TYPE_CHECKING:
    from .ayab import GuiMain

DEFAULT_PATTERN = "patterns/mushroom_36x36.png"
# the default pattern has 3 colors
KNIT_COLORS = 3
# a 2-color lace pattern, knitted after the default one
LACE_PATTERN = "patterns/kh910/10.36.png"
# language switched to at the end of the demo, before relaunching
DEMO_LANGUAGE = "fr_FR"
# set by the recorder when relaunching the app, to the language to restore
RELAUNCH_ENV = "AYAB_DEMO_RELAUNCH"
QUIT_TIMEOUT = 15000
# rows to knit before canceling (Heart of Pluto knits each row in several passes)
CANCEL_AFTER_ROWS = 5

# How long to leave things on screen (milliseconds)
SHORT = 1000
MENU = 600
STEP = 1500
LONG = 2500

# A script is a generator that yields how long to pause before resuming it
Script = Generator[int, None, None]
# A script that also returns the menu path actually shown, if known
MenuScript = Generator[int, None, "list[str] | None"]
W = TypeVar("W", bound=QWidget)


class DemoError(Exception):
    pass


def is_enabled() -> bool:
    return bool(os.environ.get("AYAB_DEMO"))


def menu_chain(action: QAction) -> list[QMenu]:
    """The menus leading to an action, from the top-level menu down."""

    def parent_menu(action: QAction) -> QMenu | None:
        # skip untitled menus, such as the menu bar's overflow menu
        for w in action.associatedObjects():
            if isinstance(w, QMenu) and w.title():
                return w
        return None

    chain: list[QMenu] = []
    menu = parent_menu(action)
    while menu is not None:
        chain.insert(0, menu)
        menu = parent_menu(menu.menuAction())
    return chain


def plain(text: str) -> str:
    """Menu text without mnemonic markers."""
    return text.replace("&", "")


def menu_path(action: QAction) -> str:
    """Describe a menu action the way a user would see it, e.g. 'Tools › Knit'."""
    parts = [menu.title() for menu in menu_chain(action)] + [action.text()]
    return " › ".join(plain(part) for part in parts)


class DemoScript(QObject):
    def __init__(self, gui: GuiMain):
        super().__init__(gui)
        self.gui = gui
        self.menu_bar = gui.menu
        self.menu = gui.menu.ui
        self.logger = logging.getLogger("demo")
        self.failed = False
        self.finished = False
        self.script = self.run_script()

        # Dismiss unexpected message boxes (e.g. new version available)
        self.popup_timer = QTimer(self)
        self.popup_timer.setInterval(250)
        self.popup_timer.timeout.connect(self.check_popup)
        self.popup_seen: QMessageBox | None = None

        timeout = int(os.environ.get("AYAB_DEMO_TIMEOUT", "300"))
        self.watchdog = QTimer(self)
        self.watchdog.setSingleShot(True)
        self.watchdog.timeout.connect(self.on_timeout)
        self.watchdog.start(timeout * 1000)

        self.knit_outcome: bool | None = None
        gui.signal_receiver.operation_finisher.connect(self.on_operation_finished)

    def start(self) -> None:
        self.logger.info("Starting demo script")
        self.popup_timer.start()
        self.resume()

    def resume(self) -> None:
        if self.finished:
            return
        try:
            delay = next(self.script)
        except StopIteration:
            self.finish(not self.failed)
            return
        except Exception:
            self.logger.exception("Demo script failed")
            self.finish(False)
            return
        QTimer.singleShot(delay, self.resume)

    # Script

    def run_script(self) -> Script:
        # leave some time for the window to show up and settle
        yield 2 * STEP
        self.gui.raise_()
        self.gui.activateWindow()
        if RELAUNCH_ENV in os.environ:
            yield from self.after_relaunch(os.environ[RELAUNCH_ENV])
            return
        scheme = QGuiApplication.styleHints().colorScheme().name
        self.step(f"AYAB demo — color scheme: {scheme}")
        yield STEP

        yield from self.show_about()
        yield from self.show_preferences()
        yield from self.show_firmware_flash()
        yield from self.select_simulation()
        yield from self.run_hardware_test()
        yield from self.load_pattern()
        yield from self.transform_image()
        # start again from the original pattern, to keep knitting short
        yield from self.load_pattern()
        yield from self.zoom()
        yield from self.knit(Mode.HEARTOFPLUTO_RIBBER, KNIT_COLORS)
        yield from self.load_pattern(LACE_PATTERN)
        yield from self.knit(Mode.SINGLEBED, 2)
        original_language = self.gui.prefs.value("language")
        yield from self.switch_language(DEMO_LANGUAGE)
        # have the recorder relaunch the app (see after_relaunch)
        yield from self.quit_app(f"relaunch\n{original_language}")

    def after_relaunch(self, original_language: str) -> Script:
        """Show the app relaunched in another language, then quit."""
        # Restore the language right away, so that the next launches are not
        # affected; this does not change the language of the running app.
        language = self.gui.prefs.value("language")
        self.gui.prefs.settings.setValue("language", original_language)
        self.step(f"Relaunched AYAB — {QLocale(language).nativeLanguageName()}")
        yield 2 * LONG
        yield from self.quit_app("success")

    def show_about(self) -> Script:
        yield from self.trigger(self.menu.action_about)
        yield LONG
        self.step("Close About box")
        self.gui.about.close()
        yield SHORT

    def show_preferences(self) -> Script:
        # The preferences dialog is modal and blocks in `exec()`,
        # so trigger it from the event loop rather than from here.
        yield from self.trigger(self.menu.action_set_preferences, later=True)
        dialog = yield from self.wait_for_modal(QDialog)
        yield LONG
        self.step("Close Preferences")
        dialog.accept()
        yield SHORT

    def show_firmware_flash(self) -> Script:
        yield from self.trigger(self.menu.action_load_AYAB_firmware)
        flash = self.gui.flash
        yield from self.wait_until(flash.isVisible, "Firmware Flash dialog")
        yield STEP
        controllers = flash.ui.controller_list
        if controllers.count() > 0:
            item = controllers.item(0)
            self.step(f"Select controller: {item.text()}")
            controllers.setCurrentItem(item)
            flash.controller_item_activated(item)
            yield STEP
        self.step("Close Firmware dialog")
        flash.close()
        yield SHORT

    def select_simulation(self) -> Script:
        simulation = QCoreApplication.translate("KnitEngine", "Simulation")
        dropdown = self.gui.engine.ui.serial_port_dropdown
        if dropdown.currentText() == simulation:
            return
        self.step(f"Port Selection: {simulation}")
        index = dropdown.findText(simulation)
        if index < 0:
            raise DemoError("Simulation port not found")
        dropdown.setCurrentIndex(index)
        yield STEP

    def run_hardware_test(self) -> Script:
        yield from self.trigger(self.menu.action_test_AYAB_device)
        hw_test = self.gui.hw_test
        yield from self.wait_until(hw_test.isVisible, "Hardware Test dialog")
        yield STEP

        def click(command: str, label: str | None = None) -> None:
            self.step(f"Hardware Test: {label or command}")
            getattr(hw_test, f"_{command}_button").click()

        for command in ["readEOLsensors", "readEncoders", "beep"]:
            click(command)
            yield STEP
        click("autoRead", "autoRead (start)")
        yield 2 * LONG
        click("autoRead", "autoRead (stop)")
        yield SHORT
        click("quit")
        yield from self.wait_until(
            lambda: not self.gui.test_thread.isRunning(), "end of hardware test"
        )
        yield SHORT

    def load_pattern(self, resource: str | None = None) -> Script:
        if resource:
            pattern = self.gui.app_context.get_resource(resource)
        else:
            pattern = os.environ.get(
                "AYAB_DEMO_PATTERN"
            ) or self.gui.app_context.get_resource(DEFAULT_PATTERN)
        action = self.menu.action_open_image_file
        self.step(f"{menu_path(action)}: {basename(pattern)}")
        # show the menu, but load the file directly rather than through
        # the file dialog
        yield from self.open_menus(action)
        self.gui.scene.ayabimage.load(pattern)
        yield STEP

    def transform_image(self) -> Script:
        for action in [
            self.menu.action_invert,
            self.menu.action_invert,
            self.menu.action_hflip,
            self.menu.action_vflip,
            self.menu.action_rotate_left,
            self.menu.action_rotate_right,
        ]:
            yield from self.trigger(action)
            yield STEP

        for action in [self.menu.action_repeat, self.menu.action_stretch]:
            yield from self.trigger(action, later=True)
            # two dialogs: vertical, then horizontal
            for _ in range(2):
                input_dialog = yield from self.wait_for_modal(QInputDialog)
                yield SHORT
                input_dialog.setIntValue(2)
                self.step(f"{menu_path(action)}: {input_dialog.labelText()} × 2")
                yield STEP
                input_dialog.accept()
                yield from self.wait_until_closed(input_dialog, action.text())
            yield STEP

        yield from self.trigger(self.menu.action_reflect, later=True)
        dialog = yield from self.wait_for_modal(QDialog)
        yield SHORT
        for checkbox in dialog.findChildren(QCheckBox)[:2]:
            checkbox.setChecked(True)
            yield SHORT
        dialog.accept()
        yield STEP

    def zoom(self) -> Script:
        for action in [
            self.menu.action_zoom_in,
            self.menu.action_zoom_in,
            self.menu.action_zoom_out,
            self.menu.action_zoom_in,
        ]:
            yield from self.trigger(action)
            yield SHORT

    def knit(self, mode: Mode, colors: int) -> Script:
        """Start knitting the current pattern, then cancel after a few rows."""
        # don't depend on whatever preferences may be stored on this machine
        options = self.gui.engine.config.ui
        options.knitting_mode_box.setCurrentIndex(mode.value)
        options.color_edit.setValue(colors)
        options.inf_repeat_checkbox.setChecked(False)
        mode_name = options.knitting_mode_box.currentText()
        self.step(f"Settings: {mode_name}, {colors} colors, no infinite repeat")
        yield STEP
        yield from self.select_simulation()

        button = self.gui.ui.knit_button
        self.step(f"Click {button.text().replace('&', '')}")
        if not button.isEnabled():
            raise DemoError("Knit button is disabled")
        self.knit_outcome = None
        button.click()

        # Knit a few rows, then cancel. The status may still show the previous
        # knitting's progress until the first update, so wait for it to restart.
        status = self.gui.engine.status
        yield from self.wait_until(
            lambda: status.current_row <= CANCEL_AFTER_ROWS
            or self.knit_outcome is not None,
            "start of knitting",
        )
        yield from self.wait_until(
            lambda: status.current_row > CANCEL_AFTER_ROWS
            or self.knit_outcome is not None,
            f"row {CANCEL_AFTER_ROWS}",
            timeout=None,
        )
        if self.knit_outcome is not None:
            raise DemoError("Knitting stopped before it could be canceled")
        yield from self.trigger(self.menu.action_cancel)
        yield from self.wait_until(
            lambda: self.knit_outcome is not None, "end of knitting"
        )
        if self.knit_outcome:
            raise DemoError("Knitting completed although it was canceled")
        self.step("Knitting canceled")
        # linger on the final state for a moment
        yield 2 * STEP

    def switch_language(self, language: str) -> Script:
        yield from self.trigger(self.menu.action_set_preferences, later=True)
        dialog = yield from self.wait_for_modal(QDialog)
        yield SHORT
        combo = dialog.findChild(PrefsLangWidget)
        if not isinstance(combo, PrefsLangWidget):
            raise DemoError("Language setting not found")
        index = combo.findData(language)
        if index < 0:
            raise DemoError(f"Language {language} not available")
        self.step(f"Language: {combo.itemText(index)}")
        combo.showPopup()
        yield STEP
        combo.setCurrentIndex(index)
        combo.hidePopup()
        yield STEP
        self.step("Close Preferences")
        dialog.accept()
        yield SHORT

    def quit_app(self, result: str) -> Script:
        """Quit through the menu, reporting `result` to the recorder."""
        action = self.menu.action_quit
        yield from self.select(action)
        self.stop(result)
        QTimer.singleShot(0, action.trigger)
        # in case quitting does not work
        QTimer.singleShot(QUIT_TIMEOUT, lambda: self.exit_after_failed_quit())

    def exit_after_failed_quit(self) -> None:
        self.logger.error("App did not quit")
        self.write_result("failure")
        QCoreApplication.exit(1)

    # Helpers

    def step(self, name: str, retitle: bool = False) -> None:
        """Describe the current step.

        With `retitle`, rename the current step rather than starting a new one.
        """
        self.logger.info(f"Demo step: {name}")
        steps_file = os.environ.get("AYAB_DEMO_STEPS")
        if steps_file:
            with open(steps_file, "a", encoding="utf-8") as f:
                record = {"t": time.time(), "step": name, "retitle": retitle}
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def trigger(self, action: QAction, later: bool = False) -> Script:
        """Select a menu action, showing the menus opening as a user would.

        Use `later=True` for actions that open a modal dialog with `exec()`,
        since that would block until the dialog is closed.
        """
        yield from self.select(action)
        if later:
            QTimer.singleShot(0, action.trigger)
        else:
            action.trigger()

    def select(self, action: QAction) -> Script:
        """Describe a menu action and show its menus, without triggering it."""
        description = menu_path(action)
        self.step(description)
        path = yield from self.open_menus(action)
        # Native menus may differ: on macOS, About, Preferences and Quit are
        # moved to the application menu.
        if path and " › ".join(path) != description:
            self.step(" › ".join(path), retitle=True)

    def open_menus(self, action: QAction) -> MenuScript:
        """Open the menus leading to an action and highlight it, then close them."""
        chain = menu_chain(action)
        if chain and self.menu_bar.isNativeMenuBar():
            return (yield from self.open_native_menus(action, chain))
        if not chain or self.menu_bar.actionGeometry(chain[0].menuAction()).isEmpty():
            # not reachable from the menu bar (e.g. in the overflow menu)
            return None
        self.gui.activateWindow()
        self.menu_bar.setActiveAction(chain[0].menuAction())
        yield MENU
        for parent, child in zip(chain, chain[1:]):
            parent.setActiveAction(child.menuAction())
            yield MENU
        chain[-1].setActiveAction(action)
        yield MENU
        for menu in reversed(chain):
            menu.hide()
        self.menu_bar.setActiveAction(None)  # type: ignore[arg-type]
        return None

    def open_native_menus(self, action: QAction, chain: list[QMenu]) -> MenuScript:
        """Have the recorder show a native (macOS) menu being used.

        Qt cannot open native menus, so this asks utils/record_demo.py, which
        uses System Events, through files in `AYAB_DEMO_MENU_DIR`.
        """
        directory = os.environ.get("AYAB_DEMO_MENU_DIR")
        if not directory:
            return None
        request = os.path.join(directory, "request.json")
        response = os.path.join(directory, "response.json")
        with open(request + ".tmp", "w") as f:
            json.dump(
                {
                    "pid": os.getpid(),
                    "menus": [plain(menu.title()) for menu in chain],
                    "item": plain(action.text()),
                    "role": action.menuRole().name,
                },
                f,
            )
        os.replace(request + ".tmp", request)
        yield from self.wait_until(
            lambda: os.path.exists(response), "native menu", timeout=20000
        )
        with open(response) as f:
            path: list[str] | None = json.load(f).get("path")
        os.remove(response)
        return path

    def wait_until(
        self,
        condition: Callable[[], bool],
        what: str,
        timeout: int | None = 10000,
    ) -> Script:
        waited = 0
        while not condition():
            if timeout is not None and waited >= timeout:
                raise DemoError(f"Timed out waiting for {what}")
            yield 100
            waited += 100

    def wait_for_modal(self, cls: type[W]) -> Generator[int, None, W]:
        yield from self.wait_until(
            lambda: isinstance(QApplication.activeModalWidget(), cls),
            f"modal {cls.__name__}",
        )
        widget = QApplication.activeModalWidget()
        assert isinstance(widget, cls)
        return widget

    def wait_until_closed(self, dialog: QWidget, what: str) -> Script:
        yield from self.wait_until(
            lambda: QApplication.activeModalWidget() is not dialog, f"{what} dialog"
        )

    # Monitoring

    def check_popup(self) -> None:
        """Dismiss message boxes after letting them show for a while."""
        widget = QApplication.activeModalWidget()
        if not isinstance(widget, QMessageBox):
            self.popup_seen = None
            return
        if widget is self.popup_seen:
            return
        self.popup_seen = widget
        self.logger.info(f"Popup: {widget.text()!r}")
        if widget.icon() == QMessageBox.Icon.Critical:
            self.failed = True
        QTimer.singleShot(LONG, lambda: self.dismiss(widget))

    def dismiss(self, box: QMessageBox) -> None:
        if QApplication.activeModalWidget() is box:
            box.done(QMessageBox.StandardButton.Ok)

    def on_operation_finished(self, operation: Operation) -> None:
        if operation != Operation.KNIT:
            return
        completed = self.gui.engine.control.notification == Output.KNITTING_FINISHED
        self.logger.info(f"Knitting operation finished, completed={completed}")
        self.knit_outcome = completed

    def on_timeout(self) -> None:
        self.logger.error("Demo timed out")
        self.finish(False)

    def finish(self, success: bool) -> None:
        if self.finished:
            return
        self.stop("success" if success else "failure")
        QCoreApplication.exit(0 if success else 1)

    def stop(self, result: str) -> None:
        """Stop the demo and report its result, leaving the app running."""
        self.finished = True
        self.logger.info(f"Demo finished: {result.splitlines()[0]}")
        self.watchdog.stop()
        self.popup_timer.stop()
        # close any modal dialog that would prevent the app from quitting
        modal = QApplication.activeModalWidget()
        if isinstance(modal, QDialog):
            modal.reject()
        # make sure worker threads are not left running
        self.gui.engine.cancel()
        self.gui.knit_thread.wait(5000)
        self.gui.test_thread.wait(5000)
        self.write_result(result)

    def write_result(self, result: str) -> None:
        result_file = os.environ.get("AYAB_DEMO_RESULT")
        if result_file:
            with open(result_file, "w") as f:
                f.write(result)
