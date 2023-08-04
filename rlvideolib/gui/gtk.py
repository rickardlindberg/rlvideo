from collections import namedtuple
import os
import sys

import gi
import mlt
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib

from rlvideolib.domain.project import Project
from rlvideolib.gui.framework import Action
from rlvideolib.gui.framework import MenuItem
from rlvideolib.gui.framework import RectangleMap
from rlvideolib.gui.generic import GUI_SPACING
from rlvideolib.gui.generic import Timeline
from rlvideolib.jobs import BackgroundWorker

class GtkGui:

    def __init__(self, event):
        self.event = event

    def show_context_menu(self, menu):
        """
        >>> event = namedtuple("FakeEvent", "button,time")(3, 0)
        >>> GtkGui(event).show_context_menu([
        ...     MenuItem(label="over", action=lambda: print("over")),
        ...     MenuItem(label="under", action=lambda: print("under")),
        ... ])
        """
        def create_gtk_handler(menu_item):
            def handler(widget):
                menu_item.action()
            return handler
        gtk_menu = Gtk.Menu()
        for menu_item in menu:
            gtk_menu_item = Gtk.MenuItem(label=menu_item.label)
            gtk_menu_item.connect("activate", create_gtk_handler(menu_item))
            gtk_menu_item.show()
            gtk_menu.append(gtk_menu_item)
        gtk_menu.popup(None, None, None, None, self.event.button, self.event.time)

class App:

    def run(self):

        mlt.Factory().init()

        if sys.argv[1:2] == ["--export-melt"]:
            path = sys.argv[2]
            print(f"Exporting {path}")
            project = Project.load(args=sys.argv[3:])
            consumer = mlt.Consumer(project.profile, "xml")
            consumer.set("resource", path)
            consumer.connect(project.get_preview_mlt_producer())
            consumer.start()
            while consumer.is_stopped() == 0:
                time.sleep(0.5)
            print("Done")
            return

        def key_press_handler(window, event):
            # TODO: return True to mark event as handled?
            if event.get_keyval().keyval == Gdk.keyval_from_name("0"):
                mlt_player.seek_beginning()
            elif event.get_keyval().keyval == Gdk.keyval_from_name("1"):
                mlt_player.play_pause(1)
            elif event.get_keyval().keyval == Gdk.keyval_from_name("2"):
                mlt_player.play_pause(2)
            elif event.get_keyval().keyval == Gdk.keyval_from_name("Left"):
                mlt_player.seek_left_one_frame()
            elif event.get_keyval().keyval == Gdk.keyval_from_name("Right"):
                mlt_player.seek_right_one_frame()

        main_window = Gtk.Window()
        main_window.set_default_size(700, 400)
        main_window.connect("destroy", Gtk.main_quit)
        main_window.connect("key_press_event", key_press_handler)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=GUI_SPACING)
        main_window.add(box)

        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=GUI_SPACING)
        box.pack_start(hbox, True, True, 0)

        def export_click(widget):
            self.project.export()
            timeline.grab_focus()
        export_button = Gtk.Button(label="Export")
        export_button.connect("clicked", export_click)
        hbox.pack_start(export_button, True, True, 0)

        preview = Gtk.DrawingArea()
        hbox.pack_start(preview, True, True, 0)

        def timeline_draw(context, rectangle_map):
            self.timeline.draw_cairo(
                context=context,
                player=mlt_player,
                width=timeline.get_allocated_width(),
                height=timeline.get_allocated_height(),
            )
        def timeline_scroll(widget, event):
            if event.direction == Gdk.ScrollDirection.UP:
                self.timeline.scroll_up(event.x, event.y)
            elif event.direction == Gdk.ScrollDirection.DOWN:
                self.timeline.scroll_down(event.x, event.y)
        timeline = CustomDrawWidget(
            main_window=main_window,
            custom_draw_handler=timeline_draw,
        )
        timeline.connect("scroll-event", timeline_scroll)
        timeline.set_can_focus(True)
        timeline.grab_focus()
        def redraw():
            timeline.queue_draw()
            return True
        refresh_id = GLib.timeout_add(100, redraw)
        box.pack_start(timeline, True, True, 0)

        statusbar = Gtk.Statusbar()
        status_context = statusbar.get_context_id("status")
        box.pack_start(statusbar, False, True, 0)
        def display_status(message):
            statusbar.pop(status_context)
            statusbar.push(status_context, message)

        main_window.show_all()

        def gtk_on_main_thread(fn, *args):
            def callback():
                fn(*args)
                return False # To only schedule it once
            GLib.idle_add(callback)
        self.project = Project.load(
            background_worker=BackgroundWorker(display_status, gtk_on_main_thread),
            args=sys.argv[1:]
        )

        self.project.on_project_data(timeline.queue_draw)

        mlt_player = MltPlayer(self.project, preview.get_window().get_xid())

        self.timeline = Timeline(
            project=self.project,
            player=mlt_player,
            rectangle_map=timeline.rectangle_map
        )
        self.timeline.set_zoom_factor(25)
        self.timeline.on_scrollbar(timeline.queue_draw)

        def delete_event(widget, event):
            # If we don't stop the player here, we might get a segfault in a
            # thread inside MLT.
            # TODO: how can we express this in code instead of a comment?
            mlt_player.stop()
        main_window.connect("delete-event", delete_event)

        Gtk.main()


class MltPlayer:

    # TODO: extract parts that don't depend on GTK

    def __init__(self, project, window_id):
        # TODO: player area outside video don't always refresh
        # TODO: figure out why SDL consumer seems to produce brighter images (black -> grey)
        self.project = project
        os.putenv("SDL_WINDOWID", str(window_id))
        self.consumer = mlt.Consumer(self.project.get_preview_profile(), "sdl")
        self.consumer.start()
        self.producer = None
        self.project.on_producer_changed(self.update_producer)

    def position(self):
        # TODO: why is this position on the producer and not the consumer?
        return self.producer.position()

    def play_pause(self, speed):
        if self.producer.get_speed() == 0:
            print("Play")
            self.producer.set_speed(speed)
        else:
            print("Pause")
            self.producer.set_speed(0)

    def scrub(self, position):
        print(f"Scrub {position}")
        self.producer.set_speed(0)
        self.producer.seek(position)

    def seek_left_one_frame(self):
        print("Left")
        self.producer.seek(self.producer.position()-1)

    def seek_right_one_frame(self):
        print("Right")
        self.producer.seek(self.producer.position()+1)

    def seek_beginning(self):
        print("Seek 0")
        self.producer.seek(0)

    def update_producer(self):
        # TODO: creating the producer here sometimes yield a segfault
        #
        #     0x00007fffe917b3c5 in mlt_multitrack_refresh () from /lib64/libmlt.so.6
        #     (gdb) bt
        #     #0  0x00007fffe917b3c5 in mlt_multitrack_refresh () at /lib64/libmlt.so.6
        #     #1  0x00007fffe917bf99 in mlt_tractor_refresh () at /lib64/libmlt.so.6
        #     #2  0x00007fffe916eacb in mlt_events_fire () at /lib64/libmlt.so.6
        #     #3  0x00007fffe916ea91 in mlt_events_fire () at /lib64/libmlt.so.6
        #
        # My suspicion is that we try to set the position of a proxy producer
        # and they interfere with each other.
        #
        # Solution? Try disconnect and purge before moving on.
        self.consumer.disconnect_all_producers()
        self.consumer.purge()
        producer = self.project.get_preview_mlt_producer()
        if self.producer:
            producer.seek(self.position())
            producer.set_speed(self.producer.get_speed())
        self.producer = producer
        self.consumer.connect(self.producer)

    def stop(self):
        self.consumer.stop()
        while self.consumer.is_stopped() == 0:
            time.sleep(0.1)

class CustomDrawWidget(Gtk.DrawingArea):

    def __init__(self, main_window, custom_draw_handler):
        Gtk.DrawingArea.__init__(self)
        self.add_events(
            self.get_events() |
            Gdk.EventMask.SCROLL_MASK |
            Gdk.EventMask.BUTTON_PRESS_MASK |
            Gdk.EventMask.BUTTON_RELEASE_MASK |
            Gdk.EventMask.POINTER_MOTION_MASK
        )
        self.connect("draw", self.on_draw)
        self.connect("button-press-event", self.on_button_press_event)
        self.connect("button-release-event", self.on_button_release_event)
        self.connect("motion-notify-event", self.on_motion_notify_event)
        self.rectangle_map = RectangleMap()
        self.custom_draw_handler = custom_draw_handler
        self.down_action = None
        self.main_window = main_window

    def on_draw(self, widget, context):
        self.rectangle_map.clear()
        self.custom_draw_handler(context, self.rectangle_map)

    def on_button_press_event(self, widget, event):
        x, y = self.get_coordinates_relative_self(event)
        if event.button == 1:
            self.down_action = self.rectangle_map.get(x, y, Action())
            self.down_action.left_mouse_down(x, y)
        elif event.button == 3:
            self.down_action = self.rectangle_map.get(x, y, Action())
            self.down_action.right_mouse_down(GtkGui(event))

    def on_motion_notify_event(self, widget, event):
        x, y = self.get_coordinates_relative_self(event)
        if self.down_action:
            self.down_action.mouse_move(x, y)
        else:
            self.rectangle_map.get(x, y, Action()).mouse_move(x, y)

    def on_button_release_event(self, widget, event):
        if self.down_action:
            self.down_action.mouse_up()
            self.down_action = None

    def get_coordinates_relative_self(self, event):
        return self.translate_coordinates(
            self.main_window,
            event.x,
            event.y
        )
