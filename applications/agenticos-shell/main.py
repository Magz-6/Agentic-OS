#!/usr/bin/env python3

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk


class AgenticOSShell(Gtk.Window):
    def __init__(self):
        super().__init__(title="AgenticOS")

        self.set_default_size(1000, 650)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.connect("destroy", Gtk.main_quit)

        label = Gtk.Label()
        label.set_markup(
            "<span size='24000' weight='bold'>AgenticOS</span>\n"
            "<span size='12000'>Native System Shell</span>"
        )

        self.add(label)


if __name__ == "__main__":
    window = AgenticOSShell()
    window.show_all()
    Gtk.main()
