#!/usr/bin/env python

# Copyright (C) 2024-2026 Dino Duratović <dinomol at mail dot com>
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
import argparse
import shutil
import gi

gi.require_version("Wp", "0.5")
from gi.repository import Wp
from gi.repository import GLib

#def get_options():
#    description_string = "Displays a volume tray icon"
#    parser = argparse.ArgumentParser(description=description_string)
#    parser.add_argument(
#        "-m",
#        "--mixer",
#        default=None,
#        help="Mixer application to show on middle click"
#        )
#    args = parser.parse_args()
#    return args


class Pipewire_Interface():
    MODULES = [
        ("libwireplumber-module-default-nodes-api", "default-nodes-api"),
        ("libwireplumber-module-mixer-api", "mixer-api"),
    ]

    def __init__(self):
        Wp.init(Wp.InitFlags.PIPEWIRE | Wp.InitFlags.SPA_TYPES)

        self.core = Wp.Core.new(None, None, None)
        self.loop = GLib.MainLoop()
        self.plugins = {}

        self.core.connect_after("connected", self.on_connected)
        self.core.connect()
        self.loop.run()

    def show_volume(self, *_):
        # TODO: move sink_id getting to a method
        sink_id = self.plugins["default-nodes-api"].emit("get-default-node", "Audio/Sink")
        result = self.plugins["mixer-api"].emit("get-volume", sink_id)

        data = result.unpack()
        volume = data.get("volume", 0.0)
        muted = data.get("mute", False)

        print(volume, muted, sink_id)

    def on_connected(self, *_):
        self.load_modules()

    def load_modules(self):
        self.pending = len(self.MODULES)
        for module, provides in self.MODULES:
            self.core.load_component(module, "module", None, provides, None, self.on_loaded)

    def on_loaded(self, core, result, *_):
        core.load_component_finish(result)
        self.pending -= 1
        if self.pending == 0:
            self.activate_plugins()

    def activate_plugins(self):
        self.pending = len(self.MODULES)
        for _module, name in self.MODULES:
            plugin = Wp.Plugin.find(self.core, name)
            self.plugins[name] = plugin
            plugin.activate(Wp.PluginFeatures.ENABLED, None, self.on_activated)

    def on_activated(self, plugin, result, *_):
        plugin.activate_finish(result)
        self.pending -= 1
        if self.pending == 0:
            self.plugins["mixer-api"].set_property("scale", 1)
            self.plugins["mixer-api"].connect("changed", self.show_volume)

            self.plugins["default-nodes-api"].connect("changed", self.show_volume)

#class Wolumeicon:
#    """Displays a tray icon which provides useful functions.
#
#    Middle clicking starts an optional mixer application.
#    Right clicking displays a quit button.
#    """
#    application_name = "Wolumeicon"
#
#    def __init__(self, mixer_application):
#        """Creates the PipeWire interface and sets up UI elements."""
#        self.application = QtWidgets.QApplication([])
#        self.mixer_application = mixer_application
#
#        self.create_tray_icon()
#        self.create_context_menu()
#        self.notifications = Notification()
#
#        self.application.exec()
#
#    def create_tray_icon(self):
#        """Creates a tray icon and connects it to the tray_icon_clicked() method."""
#        # TODO: replace temporary icon name edit-undo
#        icon = QtGui.QIcon.fromTheme("edit-undo")
#        self.tray_icon = QtWidgets.QSystemTrayIcon(icon)
#        self.tray_icon.activated.connect(self.tray_icon_clicked)
#        self.tray_icon.show()
#
#    def update_tray_icon(self, icon_name):
#        """Updates the icon every time the changed() signal is emitted."""
#        icon = QtGui.QIcon.fromTheme(icon_name)
#        self.tray_icon.setIcon(icon)
#
#    def tray_icon_clicked(self, activation_reason):
#        """Handle clicking the tray icon. See create_context_menu for right-click."""
#        # middle click
#        if activation_reason == QtWidgets.QSystemTrayIcon.ActivationReason.MiddleClick:
#            self.start_mixer()
#
#    def create_context_menu(self):
#        """Shows the context menu on right-click and display a quit button."""
#        self.context_menu = QtWidgets.QMenu()
#        self.quit_button = QtGui.QAction("Quit")
#        self.quit_button.triggered.connect(self.quit_button_pressed)
#        self.context_menu.addAction(self.quit_button)
#        self.tray_icon.setContextMenu(self.context_menu)
#
#    def quit_button_pressed(self):
#        """Stop the PipeWire monitor thread and exit the GUI."""
#        self.application.quit()
#
#    def volume_notification(self, volume, muted, icon_name):
#        """Display the desktop notification."""
#        percent_volume = linear_to_percent(volume)
#        self.notifications.show_notification(percent_volume, icon_name)
#
#    def start_mixer(self):
#        """Runs the program provided via the --mixer option."""
#        if shutil.which(self.mixer_application):
#            subprocess.Popen(self.mixer_application.split(), start_new_session=True)
#        else:
#            message = ("Mixer application '{}' not found. Make sure it's "
#                       "executable and found in your $PATH")
#            print(message.format(self.mixer_application))
#
#class Notification:
#    """Simple Freedesktop desktop notification implementation via dbus."""
#    def __init__(self):
#        session_bus = dbus.SessionBus()
#        notify_obj = session_bus.get_object("org.freedesktop.Notifications", "/org/freedesktop/Notifications")
#        self.notify_iface = dbus.Interface(notify_obj, "org.freedesktop.Notifications")
#
#        self.id = 0
#        self.timeout = -1
#        # hint used for the progress bar
#        self.hints = {"value": 0}
#
#    def show_notification(self, volume, icon):
#        """Displays a notification with a progress bar showing the volume level."""
#        self.hints["value"] = volume
#        self.id = self.notify_iface.Notify(
#            Wolumeicon.application_name,
#            self.id,
#            icon,
#            "",
#            "",
#            [],
#            self.hints,
#            self.timeout
#            )

def run():
    #options = get_options()
    #app = Wolumeicon(options.mixer)
    Pipewire_Interface()

if __name__ == "__main__":
    run()
