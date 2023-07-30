from collections import namedtuple
import os
import sys

import gi
import mlt
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib

from rlvideolib.domain.project import Project
from rlvideolib.gui.generic import GUI_SPACING
from rlvideolib.gui.generic import MenuItem
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

        def key_press_handler(window, event):
            # TODO: return True to mark event as handled?
            if event.get_keyval().keyval == Gdk.keyval_from_name("0"):
                mlt_player.seek_beginning()
            elif event.get_keyval().keyval == Gdk.keyval_from_name("space"):
                mlt_player.play_pause()
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

        def timeline_draw(widget, context):
            self.timeline.draw_cairo(
                context=context,
                playhead_position=mlt_player.position(),
                width=widget.get_allocated_width(),
                height=widget.get_allocated_height(),
            )
        def timeline_motion(widget, event):
            self.timeline.mouse_move(*timeline.translate_coordinates(
                main_window,
                event.x,
                event.y
            ))
        def timeline_button(widget, event):
            # TODO: clarify what translate_coordinates do
            if event.button == 1:
                self.timeline.left_mouse_down(*timeline.translate_coordinates(
                    main_window,
                    event.x,
                    event.y
                ))
            elif event.button == 3:
                self.timeline.right_mouse_down(*timeline.translate_coordinates(
                    main_window,
                    event.x,
                    event.y
                ), GtkGui(event))
        def timeline_button_up(widget, event):
            self.timeline.mouse_up()
        def timeline_scroll(widget, event):
            if event.direction == Gdk.ScrollDirection.UP:
                self.timeline.scroll_up(event.x, event.y)
            elif event.direction == Gdk.ScrollDirection.DOWN:
                self.timeline.scroll_down(event.x, event.y)
        timeline = Gtk.DrawingArea()
        timeline.connect("draw", timeline_draw)
        timeline.connect("button-press-event", timeline_button)
        timeline.connect("button-release-event", timeline_button_up)
        timeline.connect("motion-notify-event", timeline_motion)
        timeline.connect("scroll-event", timeline_scroll)
        timeline.add_events(
            timeline.get_events() |
            Gdk.EventMask.SCROLL_MASK |
            Gdk.EventMask.BUTTON_PRESS_MASK |
            Gdk.EventMask.BUTTON_RELEASE_MASK |
            Gdk.EventMask.POINTER_MOTION_MASK
        )
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

        self.timeline = Timeline(project=self.project, player=mlt_player)
        self.timeline.set_zoom_factor(25)
        self.timeline.on_scrollbar(timeline.queue_draw)

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

    def play_pause(self):
        if self.producer.get_speed() == 0:
            print("Play")
            self.producer.set_speed(1)
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
        producer = self.project.get_preview_mlt_producer()
        if self.producer:
            producer.seek(self.position())
            producer.set_speed(self.producer.get_speed())
        self.consumer.disconnect_all_producers()
        self.producer = producer
        self.consumer.connect(self.producer)