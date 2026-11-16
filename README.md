# Wolumeicon

Wolumeicon is a simple volume tray icon written in Python and Qt6 that
works with Wayland. Wayland compatibility was the primary driving force
for creating this, since the other volume tray programs that I used 
didn't work with Wayland. It also works on PipeWire natively, which
was another reason for creating this.

~~It is a rather primitive implementation, mostly due to its PipeWire
monitoring. Since, as the time of writing this, there isn't a PipeWire Python library
and I lack the skill to create a proper solution, it's monitoring
for changes by parsing the output of `pw-mon`.~~

The previous way of detecting changes was based on parsing the output
of pw-dump, which was hacky and unreliable. I was waiting for an
easy to use Python Pipewire library, but there still isn't one. There is
however the [Wireplumber library with bindings via PyGObject](https://lazka.github.io/pgi-docs/#Wp-0.5),
but I had no idea how to use it (there are no tutorials).

I used AI to help me write this. The concept worked, but I had no idea
how or why. I still don't really know how Pipewire or Wireplumber work,
but I was able to simplify the AI solution further while trying to
grasp the basics.

Right now it hooks directly into Pipewire events and reacts to those,
which is way cleaner than the previous solution.

## How to use

* install (Arch Linux users can use [this PKGBUILD](https://raw.githubusercontent.com/dglava/pkgbuilds/master/wolumeicon-git/PKGBUILD)
* run `wolumeicon`, ideally starting it with your desktop session
* see `wolumeicon --help` for the available options

## Dependecies

* Python
* PyQt6
* Python-Dbus
* Python-gobject
* Libwireplumber
