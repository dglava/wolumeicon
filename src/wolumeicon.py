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

def get_cli_output(command):
    """Returns a str containing the output of a CLI program."""
    proc = subprocess.run(command.split(), capture_output=True, text=True)
    return proc.stdout

def get_json(command):
    """Return a dictionary with JSON data from a program (mostly pw-dump)."""
    output = get_cli_output(command)
    data = json.loads(output)
    return data

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
    """PipeWire device info, event monitoring and volume getting and setting."""
    # emitted when our device changes (volume, muted, icon name)
    changed = QtCore.pyqtSignal(float, bool, str)

    def __init__(self):
        """Gets default sink, ID and route data and current volume/mute settings."""
        super().__init__()
        self.wait_init()
        self.default_sink = self.get_default_sink()
        self.device_id = self.get_device_id()
        self.device_name = self.get_device_name()
        self.route_index, self.route_device, self.route_order = self.get_route_data()
        self.volume, self.muted = self.get_volume_and_muted()
        self.icon_name = self.choose_icon()
        self.running = False

    def wait_init(self):
        """Verifies that PipeWire has initialized.

        Hacky solution. I am not sure if this is a sufficient proof that
        PipeWire has initialized everything, but it seems to work for now.
        """
        while True:
            data = get_json("pw-dump Metadata")
            for item in data:
                if item["props"]["metadata.name"] == "default":
                    return

    def get_default_sink(self):
        """Get the default PipeWire sink."""
        data = get_json("pw-dump Metadata")
        for item in data:
            for metadata in item["metadata"]:
                if metadata["key"] == "default.audio.sink":
                    default_sink = metadata["value"]["name"]
        return default_sink

    def get_device_id(self):
        """Get the ID of our device used by default sink."""
        data = get_json("pw-dump {}".format(self.default_sink))
        device_id = data[0]["info"]["props"]["device.id"]
        return str(device_id)

    def get_device_name(self):
        """Get the name of the device used by the default sink."""
        data = get_json("pw-dump {}".format(self.device_id))
        for item in data:
            if item["id"] == int(self.device_id):
                device_name = item["info"]["props"]["device.name"]
        return device_name

    def get_route_data(self):
        """Get info about the relevant Route for volume changing."""
        data = get_json("pw-dump {}".format(self.device_name))
        for route in data[0]["info"]["params"]["Route"]:
            if route["direction"] == "Output":
                index = route["index"]
                device = route["device"]
                order = data[0]["info"]["params"]["Route"].index(route)
                return index, device, order

    def monitor(self):
        """Basic PipeWire event monitor.

        It is very primitive as it reads the stdout of pw-mon. It does
        some basic filtering, like reacting only to changes for our default
        sink/device. It emits a PyQt signal, which is utilized by the GUI
        part. Hopefully a PipeWire library for Python will be available
        eventually, with a proper event monitor that can be utilized.
        """
        # TODO: switch to QProcess?
        # TODO: watch for device_id changes, verify that it's not changed?
        pw_mon = ['pw-mon', '-o', '-N']
        process = subprocess.Popen(pw_mon, stdout=subprocess.PIPE, text=True)
        while self.running:
            if "changed" in process.stdout.readline():
                if self.device_id in process.stdout.readline():
                    self.volume, self.muted = self.get_volume_and_muted()
                    self.icon_name = self.choose_icon()
                    self.changed.emit(self.volume, self.muted, self.icon_name)

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

    def get_volume_and_muted(self):
        """Gets volume/muted information from our device.

        Relies on pw-dump until a PipeWire library becomes available.
        """
        data = get_json("pw-dump {}".format(self.device_name))
        channel_volumes = data[0]["info"]["params"]["Route"][self.route_order]["props"]["channelVolumes"]
        muted = data[0]["info"]["params"]["Route"][self.route_order]["props"]["mute"]
        # assume volume channels are always linked
        return channel_volumes[0], muted

#    def set_volume(self, volume):
#        """Set the volume for our device.
#
#        Relies on pw-cli until a PipeWire library becomes available.
#        Doesn't mute audio as it's only meant to change the
#        volume via input from the slider. Once global hotkeys work on Wayland,
#        muting should also be handled - either in here or as a separate method.
#        """
#        # double curly braces are needed for escaping
#        json_prop = "{{index: {}, device: {}, props: {{channelVolumes: [{}, {}]}}}}"
#        command = (
#            "pw-cli",
#            "s",
#            # TODO: change to self.device_name
#            self.device_id,
#            "Route",
#            json_prop.format(self.route_index, self.route_device, volume, volume)
#            )
#        subprocess.run(command, stdout=subprocess.DEVNULL)

    def choose_icon(self):
        """Gets the appropriate icon for the volume level.

        It's convenient to do it at this level, so it's available for
        the tray icon, notification icon and elsewhere where needed.
        """
        if self.muted:
            return "audio-volume-muted"
        elif self.volume > 0.405224:
            return "audio-volume-high"
        elif self.volume > 0.013824:
            return "audio-volume-medium"
        elif self.volume > 0:
            return "audio-volume-low"
        else:
            return "audio-volume-muted"

class Wolumeicon:
    """Displays a tray icon which provides useful functions.

    Left clicking shows a slider which adjusts volume.
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
#        self.create_slider()
        self.notifications = Notification()

        self.pipewire_interface.changed.connect(self.update_tray_icon)
        self.pipewire_interface.changed.connect(self.volume_notification)

        self.application.exec()

    def create_tray_icon(self):
        """Creates a tray icon and connects it to the tray_icon_clicked() method."""
        icon = QtGui.QIcon.fromTheme(self.pipewire_interface.icon_name)
        self.tray_icon = QtWidgets.QSystemTrayIcon(icon)
        self.tray_icon.activated.connect(self.tray_icon_clicked)
        self.tray_icon.show()

    def update_tray_icon(self, volume, muted, icon_name):
        """Updates the icon every time the changed() signal is emitted."""
        icon = QtGui.QIcon.fromTheme(icon_name)
        self.tray_icon.setIcon(icon)

    def tray_icon_clicked(self, activation_reason):
        """Handle clicking the tray icon. See create_context_menu for right-click."""
#        # left click
#        if activation_reason == QtWidgets.QSystemTrayIcon.ActivationReason.Trigger:
#            tray_icon_geometry = self.tray_icon.geometry()
#            x_pos = tray_icon_geometry.x()
#            y_pos = tray_icon_geometry.y() + tray_icon_geometry.height()
#            # adjust the slider's value before displaying it
#            self.update_slider_from_volume(self.pipewire_interface.volume)
#            self.slider_menu.exec(QtCore.QPoint(x_pos, y_pos))

        # middle click
        if activation_reason == QtWidgets.QSystemTrayIcon.ActivationReason.MiddleClick:
            self.start_mixer()

    def create_context_menu(self):
        """Shows the context menu on right-click and display a quit button."""
        self.context_menu = QtWidgets.QMenu()
        #self.context_menu.setStyleSheet("QMenu {padding: 2px 0}")
        self.quit_button = QtGui.QAction("Quit")
        self.quit_button.triggered.connect(self.quit_button_pressed)
        self.context_menu.addAction(self.quit_button)
        self.tray_icon.setContextMenu(self.context_menu)

    def quit_button_pressed(self):
        """Stop the PipeWire monitor thread and exit the GUI."""
        self.pipewire_interface.stop_monitor()
        self.application.quit()

#    def create_slider(self):
#        """The volume change slider."""
#        self.slider = QtWidgets.QSlider()
#        self.slider.setMaximum(100)
#        self.slider.valueChanged.connect(self.update_volume_from_slider)
#
#        self.slider_menu = QtWidgets.QMenu()
#        self.slider_action = QtWidgets.QWidgetAction(self.slider_menu)
#        self.slider_action.setDefaultWidget(self.slider)
#        self.slider_menu.addAction(self.slider_action)

#    def update_slider_from_volume(self, volume):
#        """Adjusts the slider to the current volume."""
#        value = linear_to_percent(volume)
#        self.slider.setValue(value)

#    def update_volume_from_slider(self, slider_value):
#        """Updates volumes from the slider's current value."""
#        volume = percent_to_linear(slider_value)
#        self.pipewire_interface.set_volume(volume)

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
