#!/usr/bin/env python

# Copyright (C) 2024-2025 Dino Duratović <dinomol at mail dot com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from PyQt6 import QtWidgets
from PyQt6 import QtGui
from PyQt6 import QtCore
import dbus
import subprocess
import json
import sys
import argparse
import shutil

def cli_output(command):
    """Returns a string containing the output of a CLI program."""
    process = subprocess.run(command.split(), capture_output=True, text=True)
    return process.stdout

def cube_root(number):
    return number ** (1/3)

def linear(number):
    return number * number * number

def linear_to_percent(number):
    """Convert linear volume to percent volume."""
    return int(cube_root(number) * 100)

def percent_to_linear(number):
    """Convert percent volume to linear volume."""
    return linear(number / 100)

def get_options():
    description_string = "Displays a volume tray icon"
    parser = argparse.ArgumentParser(description=description_string)
    parser.add_argument(
        "-m",
        "--mixer",
        default=None,
        help="Mixer application to show on middle click"
        )
    args = parser.parse_args()
    return args

class Pipewire_Interface(QtCore.QObject):
    changed = QtCore.pyqtSignal(float, bool, str)

    def __init__(self):
        super().__init__()
        self.wait_init()
        self.sink = self.get_sink()
        self.device_id = self.get_device_id()
        self.device_name = self.get_device_name()
        self.running = False

    def wait_init(self):
        """Verifies that PipeWire has initialized.

        Hacky solution. I am not sure if this is a sufficient proof that
        PipeWire has initialized everything, but it seems to work for now.
        """
        #TODO: perhaps find a better way to make sure pipewire is initialized
        while True:
            data = cli_output("pw-dump Metadata")
            json_data = json.loads(data)
            for item in json_data:
                if item["props"]["metadata.name"] == "default":
                    return

    def get_sink(self):
        """Get the default PipeWire sink."""
        data = cli_output("pw-dump Metadata")
        json_data = json.loads(data)
        for item in json_data:
            for metadata in item["metadata"]:
                if metadata["key"] == "default.audio.sink":
                    return metadata["value"]["name"]

    def get_device_id(self):
        """Get the ID of our device used by default sink."""
        data = cli_output("pw-dump {}".format(self.sink))
        json_data = json.loads(data)
        device_id = json_data[0]["info"]["props"]["device.id"]
        return device_id

    def get_device_name(self):
        """Get the name of the device used by the default sink."""
        data = cli_output("pw-dump {}".format(self.device_id))
        json_data = json.loads(data)
        for item in json_data:
            if item["id"] == self.device_id:
                device_name = item["info"]["props"]["device.name"]
        return device_name

    def get_volume_and_muted(self, data):
        """Gets volume/muted information from our device.

        data is a JSON object with pw-dump data for our device."""
        #TODO: does filtering based just on "direction" work? what if
        # there are multiple ones with "Output"?
        for route in data[0]["info"]["params"]["Route"]:
            if route["direction"] == "Output":
                # assume the channels are always linked, therefore [0]
                volume = route["props"]["channelVolumes"][0]
                muted = route["props"]["mute"]
                return volume, muted

    def choose_icon(self, volume, muted):
        """Gets the appropriate icon for the volume level.

        It's convenient to do it at this level, so it's available for
        the tray icon, notification icon and elsewhere where needed.
        """
        if muted:
            return "audio-volume-muted"
        elif volume > 0.405224:
            return "audio-volume-high"
        elif volume > 0.013824:
            return "audio-volume-medium"
        elif volume > 0:
            return "audio-volume-low"
        else:
            return "audio-volume-muted"

    def monitor(self):
        """Basic PipeWire event monitor.

        It is very primitive as it wait for pw-dump to react to events.
        It assembles the JSON output by pw-dump line by line. Each block
        starts with [ and ends with ]. Once a block is done, it reads it
        and gets volume/muted/icon information from it.
        It emits a PyQt signal, which is utilized by the GUI part.
        Hopefully a PipeWire library for Python will be available eventually,
        with a proper event monito that can be utilized.
        """
        pw_dump = ["pw-dump", "-Nm", self.device_name]
        buffer = ""
        process = subprocess.Popen(pw_dump, stdout=subprocess.PIPE, text=True)
        while self.running:
            line = process.stdout.readline()
            buffer += line
            # the JSON has ended
            if line.startswith("]"):
                data = json.loads(buffer)
                self.volume, self.muted = self.get_volume_and_muted(data)
                self.icon = self.choose_icon(self.volume, self.muted)
                self.changed.emit(self.volume, self.muted, self.icon)
                # clears the buffer, start reading new JSON
                buffer = ""

    def start_monitor(self):
        """Starts the PipeWire event monitor in a separate thread."""
        self.running = True
        self.thread = QtCore.QThread()
        self.moveToThread(self.thread)
        self.thread.started.connect(self.monitor)
        self.thread.finished.connect(self.deleteLater)
        self.thread.start()

    def stop_monitor(self):
        """Stops the PipeWire event monitor thread."""
        self.running = False
        self.thread.exit()

class Wolumeicon:
    """Displays a tray icon which provides useful functions.

    Middle clicking starts an optional mixer application.
    Right clicking displays a quit button.
    """
    application_name = "Wolumeicon"

    def __init__(self, mixer_application):
        """Creates the PipeWire interface and sets up UI elements."""
        self.pipewire_interface = Pipewire_Interface()
        self.pipewire_interface.start_monitor()

        self.application = QtWidgets.QApplication([])
        self.mixer_application = mixer_application

        self.create_tray_icon()
        self.create_context_menu()
        self.notifications = Notification()

        self.pipewire_interface.changed.connect(self.update_tray_icon)
        self.pipewire_interface.changed.connect(self.volume_notification)

        self.application.exec()

    def create_tray_icon(self):
        """Creates a tray icon and connects it to the tray_icon_clicked() method."""
        icon = QtGui.QIcon.fromTheme(self.pipewire_interface.icon)
        self.tray_icon = QtWidgets.QSystemTrayIcon(icon)
        self.tray_icon.activated.connect(self.tray_icon_clicked)
        self.tray_icon.show()

    def update_tray_icon(self, volume, muted, icon_name):
        """Updates the icon every time the changed() signal is emitted."""
        icon = QtGui.QIcon.fromTheme(icon_name)
        self.tray_icon.setIcon(icon)

    def tray_icon_clicked(self, activation_reason):
        """Handle clicking the tray icon. See create_context_menu for right-click."""
        # middle click
        if activation_reason == QtWidgets.QSystemTrayIcon.ActivationReason.MiddleClick:
            self.start_mixer()

    def create_context_menu(self):
        """Shows the context menu on right-click and display a quit button."""
        self.context_menu = QtWidgets.QMenu()
        self.quit_button = QtGui.QAction("Quit")
        self.quit_button.triggered.connect(self.quit_button_pressed)
        self.context_menu.addAction(self.quit_button)
        self.tray_icon.setContextMenu(self.context_menu)

    def quit_button_pressed(self):
        """Stop the PipeWire monitor thread and exit the GUI."""
        self.pipewire_interface.stop_monitor()
        self.application.quit()

    def volume_notification(self, volume, muted, icon_name):
        """Display the desktop notification."""
        percent_volume = linear_to_percent(volume)
        self.notifications.show_notification(percent_volume, icon_name)

    def start_mixer(self):
        """Runs the program provided via the --mixer option."""
        if shutil.which(self.mixer_application):
            subprocess.Popen(self.mixer_application.split(), start_new_session=True)
        else:
            message = ("Mixer application '{}' not found. Make sure it's "
                       "executable and found in your $PATH")
            print(message.format(self.mixer_application))

class Notification:
    """Simple Freedesktop desktop notification implementation via dbus."""
    def __init__(self):
        session_bus = dbus.SessionBus()
        notify_obj = session_bus.get_object("org.freedesktop.Notifications", "/org/freedesktop/Notifications")
        self.notify_iface = dbus.Interface(notify_obj, "org.freedesktop.Notifications")

        self.id = 0
        self.timeout = -1
        # hint used for the progress bar
        self.hints = {"value": 0}

    def show_notification(self, volume, icon):
        """Displays a notification with a progress bar showing the volume level."""
        self.hints["value"] = volume
        self.id = self.notify_iface.Notify(
            Wolumeicon.application_name,
            self.id,
            icon,
            "",
            "",
            [],
            self.hints,
            self.timeout
            )

def run():
    options = get_options()
    app = Wolumeicon(options.mixer)

if __name__ == "__main__":
    run()
