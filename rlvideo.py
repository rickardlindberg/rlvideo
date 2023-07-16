from collections import namedtuple
import os
import sys
import threading

import cairo
import gi
import mlt
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib

from rlvideolib.debug import timeit
from rlvideolib.domain.project import Project
from rlvideolib.domain.region import Region
from rlvideolib.events import Event
from rlvideolib.graphics.rectangle import Rectangle
from rlvideolib.graphics.rectangle import RectangleMap

class App:

    def run(self):

        mlt.Factory().init()

        def key_press_handler(window, event):
            if event.get_keyval().keyval == Gdk.keyval_from_name("0"):
                mlt_player.seek_beginning()
            elif event.get_keyval().keyval == Gdk.keyval_from_name("space"):
                mlt_player.play_pause()
            elif event.get_keyval().keyval == Gdk.keyval_from_name("Left"):
                mlt_player.seek_left_one_frame()
            elif event.get_keyval().keyval == Gdk.keyval_from_name("Right"):
                mlt_player.seek_right_one_frame()

        main_window = Gtk.Window()
        main_window.connect("destroy", Gtk.main_quit)
        main_window.connect("key_press_event", key_press_handler)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        main_window.add(box)

        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        box.pack_start(hbox, True, True, 0)

        def export_click(widget):
            self.project.export()
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
            self.timeline.mouse_down(*timeline.translate_coordinates(
                main_window,
                event.x,
                event.y
            ))
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

        self.project = Project.load(
            background_worker=BackgroundWorker(display_status),
            args=sys.argv[1:]
        )

        self.project.on_project_data(timeline.queue_draw)

        mlt_player = MltPlayer(self.project, preview.get_window().get_xid())

        self.timeline = Timeline(project=self.project, player=mlt_player)
        self.timeline.set_zoom_factor(25)
        self.timeline.on_scrollbar(timeline.queue_draw)

        Gtk.main()

class MltPlayer:

    def __init__(self, project, window_id):
        # TODO: player area outside video don't always refresh
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
        print("Scrub")
        self.producer.set_speed(0)
        self.producer.seek(position)

    def seek_left_one_frame(self):
        print("Left")
        self.producer.seek(self.producer.position()-1)

    def seek_right_one_frame(self):
        # TODO: how to seek right beyond the last frame (to position cursor for
        # insertion for example)?
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
        producer.set("eof", "loop")
        self.producer = producer
        self.consumer.disconnect_all_producers()
        self.consumer.connect(self.producer)

class Timeline:

    """
    >>> _ = mlt.Factory().init()
    >>> project = Project.new()
    >>> with project.new_transaction() as transaction:
    ...     transaction.add_text_clip("hello", length=10, id="hello")
    >>> timeline = Timeline(project=project, player=None)
    >>> width, height = 300, 100
    >>> surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
    >>> context = cairo.Context(surface)
    >>> timeline.draw_cairo(
    ...     context=context,
    ...     playhead_position=0,
    ...     width=width,
    ...     height=height
    ... )
    >>> timeline.rectangle_map # doctest: +ELLIPSIS
    Rectangle(x=10, y=20, width=10, height=20):
      Cut(source=CutSource(source_id='hello'), in_out=Region(start=0, end=10), position=0, id=...)
    Rectangle(x=10, y=10, width=280, height=20):
      scrub
    Rectangle(x=10, y=60, width=7840, height=30):
      position
    >>> timeline.split_into_sections().to_ascii_canvas()
    |<-h0----->|
    >>> timeline.mouse_down(15, 25)
    >>> timeline.mouse_move(16, 26)
    >>> timeline.mouse_up()
    >>> timeline.split_into_sections().to_ascii_canvas()
    |%<-h0----->|
    >>> timeline.mouse_move(17, 27)
    >>> timeline.split_into_sections().to_ascii_canvas()
    |%<-h0----->|
    """

    def __init__(self, project, player):
        self.scrollbar_event = Event()
        self.project = project
        self.player = player
        self.set_scrollbar(Scrollbar(
            content_length=0,
            content_desired_start=0,
            one_length_in_pixels=1,
            ui_size=10,
        ))
        self.rectangle_map = RectangleMap()
        self.tmp_transaction = None
        self.mouse_up()

    def set_scrollbar(self, scrollbar):
        self.scrollbar = scrollbar
        self.scrollbar_event.trigger()

    def on_scrollbar(self, fn):
        self.scrollbar_event.listen(fn)
        fn()

    def mouse_down(self, x, y):
        self.tmp_xy = (x, y)
        self.tmp_scrollbar = self.scrollbar
        self.tmp_transaction = self.project.new_transaction()
        self.tmp_cut = self.rectangle_map.get(x, y)

    def mouse_move(self, x, y):
        if self.tmp_cut:
            delta = x-self.tmp_xy[0]
            if self.tmp_cut == "position":
                self.set_scrollbar(self.tmp_scrollbar.move_scrollbar(delta))
            elif self.tmp_cut == "scrub":
                self.player.scrub(
                    self.scrollbar.content_start+
                    int(x/self.scrollbar.one_length_in_pixels)
                )
            else:
                self.tmp_transaction.rollback()
                self.tmp_transaction.modify(self.tmp_cut.id, lambda x:
                    x.move(int(delta/self.scrollbar.one_length_in_pixels)))

    def mouse_up(self):
        if self.tmp_transaction:
            self.tmp_transaction.commit()
        self.tmp_xy = None
        self.tmp_scrollbar= None
        self.tmp_transaction = None
        self.tmp_cut = None

    def scroll_up(self, x, y):
        self.set_zoom_factor(self.scrollbar.one_length_in_pixels*1.5)

    def scroll_down(self, x, y):
        self.set_zoom_factor(self.scrollbar.one_length_in_pixels/1.5)

    def set_zoom_factor(self, zoom_factor):
        self.set_scrollbar(self.scrollbar._replace(one_length_in_pixels=zoom_factor))

    def split_into_sections(self):
        return self.project.split_into_sections()

    @timeit("Timeline.draw_cairo")
    def draw_cairo(self, context, playhead_position, width, height):
        """
        >>> _ = mlt.Factory().init()
        >>> width, height = 300, 100
        >>> surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
        >>> context = cairo.Context(surface)
        >>> project = Project.new()
        >>> with project.new_transaction() as transaction:
        ...     transaction.add_text_clip("hello", length=10)
        >>> timeline = Timeline(project=project, player=None)
        >>> timeline.draw_cairo(
        ...     context=context,
        ...     playhead_position=0,
        ...     width=width,
        ...     height=height
        ... )
        >>> timeline.draw_cairo(
        ...     context=context,
        ...     playhead_position=0,
        ...     width=width,
        ...     height=height
        ... )
        >>> timeline.rectangle_map # doctest: +ELLIPSIS
        Rectangle(x=10, y=20, width=10, height=20):
          Cut(source=CutSource(source_id=...), in_out=Region(start=0, end=10), position=0, id=...)
        Rectangle(x=10, y=10, width=280, height=20):
          scrub
        Rectangle(x=10, y=60, width=7840, height=30):
          position
        """
        margin = 10
        area = Rectangle.from_size(width=width, height=height).deflate(margin)
        top_area, bottom_area = area.split_height_from_bottom(
            bottom_height=30,
            space=margin
        )
        sections = self.split_into_sections()

        self.scrollbar = self.scrollbar._replace(
            content_length=sections.length,
            ui_size=top_area.width
        )

        with top_area.cairo_clip_translate(context) as top_area:
            context.set_source_rgb(0.9, 0.9, 0.9)
            context.rectangle(top_area.x, top_area.y, top_area.width, top_area.height)
            context.fill()
            with top_area.deflate_height(
                amount=margin
            ).cairo_clip_translate(context) as clip_area:
                with clip_area.move(
                    dx=self.scrollbar.content_to_pixels(-self.scrollbar.content_start)
                ).resize(
                    width=self.scrollbar.content_to_pixels(sections.length)
                ).cairo_clip_translate(context) as sections_area:
                    self.rectangle_map.clear()
                    sections.draw_cairo(
                        context=context,
                        rectangle=sections_area,
                        rectangle_map=self.rectangle_map,
                        project=self.project
                    )
            context.set_source_rgb(0.1, 0.1, 0.1)
            context.move_to(self.scrollbar.content_to_pixels(playhead_position-self.scrollbar.content_start), 0)
            context.line_to(self.scrollbar.content_to_pixels(playhead_position-self.scrollbar.content_start), top_area.height)
            context.stroke()

        scrub_area = area._replace(height=margin*2)
        x, y, w, h = (
            scrub_area.x,
            scrub_area.y,
            scrub_area.width,
            scrub_area.height,
        )
        rect_x, rect_y = context.user_to_device(x, y)
        rect_w, rect_h = context.user_to_device_distance(w, h)
        self.rectangle_map.add(Rectangle(
            x=int(rect_x),
            y=int(rect_y),
            width=int(rect_w),
            height=int(rect_h)
        ), "scrub")

        with bottom_area.cairo_clip_translate(context) as area:
            x_start = self.scrollbar.region_shown.start / self.scrollbar.whole_region.length * area.width
            x_end = self.scrollbar.region_shown.end / self.scrollbar.whole_region.length * area.width

            # TODO: add callback mechanism in rectangle map
            x, y, w, h = (
                area.x+x_start,
                area.y,
                x_end-x_start,
                area.height
            )
            rect_x, rect_y = context.user_to_device(x, y)
            rect_w, rect_h = context.user_to_device_distance(w, h)
            self.rectangle_map.add(Rectangle(
                x=int(rect_x),
                y=int(rect_y),
                width=int(rect_w),
                height=int(rect_h)
            ), "position")

            context.rectangle(x, y, w, h)
            context.set_source_rgba(0.4, 0.9, 0.4, 0.5)
            context.fill()

            context.rectangle(area.x, area.y, area.width, area.height)
            context.set_source_rgb(0.1, 0.1, 0.1)
            context.stroke()

class Scrollbar(namedtuple("Scrollbar", "content_length,one_length_in_pixels,ui_size,content_desired_start")):

    # TODO: clean up Scrollbar interface

    """
    >>> zoom_scroll = Scrollbar(
    ...     content_length=10,
    ...     one_length_in_pixels=1,
    ...     ui_size=100,
    ...     content_desired_start=0
    ... )
    >>> zoom_scroll.content_start
    0
    """

    @property
    def content_start(self):
        """
        >>> Scrollbar(
        ...     content_length=100,
        ...     one_length_in_pixels=1,
        ...     ui_size=10,
        ...     content_desired_start=1
        ... ).content_start
        1

        >>> Scrollbar(
        ...     content_length=100,
        ...     one_length_in_pixels=1,
        ...     ui_size=10,
        ...     content_desired_start=-10
        ... ).content_start
        0

        >>> Scrollbar(
        ...     content_length=100,
        ...     one_length_in_pixels=1,
        ...     ui_size=10,
        ...     content_desired_start=100
        ... ).content_start
        90.0
        """
        # TODO: content_start -> x_offset | pixel_offset
        length_shown = self.ui_size / self.one_length_in_pixels
        max_start = max(0, self.content_length - length_shown)
        if self.content_desired_start < 0:
            return 0
        elif self.content_desired_start > max_start:
            return max_start
        else:
            return self.content_desired_start

    def move_scrollbar(self, pixels):
        """
        >>> Scrollbar(
        ...     content_length=100,
        ...     one_length_in_pixels=1,
        ...     ui_size=10,
        ...     content_desired_start=0
        ... ).move_scrollbar(1).content_desired_start
        10.0
        """
        one_pixel_in_length = self.content_length / self.ui_size
        delta = pixels * one_pixel_in_length
        return self._replace(
            content_desired_start=self.content_start+delta
        )

    @property
    def whole_region(self):
        if self.content_length > 0:
            return Region(start=0, end=self.content_length)
        else:
            return Region(start=0, end=10)

    @property
    def region_shown(self):
        return Region(
            start=self.content_start,
            end=self.content_start+self.ui_size/self.one_length_in_pixels
        )

    def content_to_pixels(self, length):
        return length * self.one_length_in_pixels

class BackgroundWorker:

    def __init__(self, display_status):
        self.display_status = display_status
        self.jobs = []
        self.description = None

    def add(self, description, result_fn, work_fn, *args, **kwargs):
        self.jobs.append((description, result_fn, work_fn, args, kwargs))
        self.pop()

    def pop(self):
        def result(*args):
            result_fn(*args)
            self.description = None
            self.pop()
            return False # To only schedule it once
        def worker():
            GLib.idle_add(result, work_fn(*args, **kwargs))
        if self.description is None and self.jobs:
            self.description, result_fn, work_fn, args, kwargs = self.jobs.pop(-1)
            thread = threading.Thread(target=worker)
            thread.daemon = True
            thread.start()
        if self.description:
            self.display_status(f"{self.description} {len(self.jobs)} left in queue...")
        else:
            self.display_status("Ready")

if __name__ == "__main__":
    App().run()
