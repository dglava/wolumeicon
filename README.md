# Wolumeicon

Wolumeicon is a simple volume tray icon written in Python and Qt6 that
works with Wayland. Wayland compatibility was the primary driving force
for creating this, since the other volume tray programs that I used 
didn't work with Wayland. It also works on PipeWire natively, which
was another reason for creating this.

It is a rather primitive implementation, mostly due to its PipeWire
monitoring. Since there isn't a PipeWire Python library as of writing
this (and I lack the skill to create a proper solution), it's monitoring
for changes by parsing the output of `pw-mon`.

## How to use

* install (Arch Linux users can use [this PKGBUILD](https://raw.githubusercontent.com/dglava/pkgbuilds/master/wolumeicon-git/PKGBUILD)
* run `wolumeicon`, ideally starting it with your desktop session
* see `wolumeicon --help` for the available options

## Dependecies

* Python
* PyQt6
* Python-Dbus
* PipeWire
