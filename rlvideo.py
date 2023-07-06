import os

import cairo
import gi
import mlt
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib

from rlvideolib.domain.cut import Cuts
from rlvideolib.domain.region import Region
from rlvideolib.domain.source import Source
from rlvideolib.graphics.rectangle import Rectangle
from rlvideolib.graphics.rectangle import RectangleMap

class App:

    def __init__(self):
        mlt.Factory().init()
        self.profile = mlt.Profile()
        self.timeline = Timeline.with_test_clips()

    def generate_mlt_producer(self):
        """
        >>> isinstance(App().generate_mlt_producer(), mlt.Playlist)
        True
        """
        return self.timeline.to_mlt_producer(self.profile)

    def run(self):

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

        preview = Gtk.DrawingArea()
        box.pack_start(preview, True, True, 0)

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
            mlt_player.set_producer(self.generate_mlt_producer())
            print(self.timeline.split_into_sections().to_ascii_canvas())
        timeline = Gtk.DrawingArea()
        timeline.connect("draw", timeline_draw)
        timeline.connect("button-press-event", timeline_button)
        timeline.connect("button-release-event", timeline_button_up)
        timeline.connect("motion-notify-event", timeline_motion)
        timeline.add_events(
            timeline.get_events() |
            Gdk.EventMask.BUTTON_PRESS_MASK |
            Gdk.EventMask.BUTTON_RELEASE_MASK |
            Gdk.EventMask.POINTER_MOTION_MASK
        )
        def redraw():
            timeline.queue_draw()
            return True
        refresh_id = GLib.timeout_add(100, redraw)
        box.pack_start(timeline, True, True, 0)

        main_window.show_all()

        mlt_player = MltPlayer(self.profile, preview.get_window().get_xid())
        mlt_player.set_producer(self.generate_mlt_producer())
        print(self.timeline.split_into_sections().to_ascii_canvas())

        Gtk.main()

class MltPlayer:

    def __init__(self, profile, window_id):
        self.profile = profile
        os.putenv("SDL_WINDOWID", str(window_id))
        self.consumer = mlt.Consumer(self.profile, "sdl")
        self.consumer.start()
        self.producer = None

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

    def set_producer(self, producer):
        if self.producer:
            producer.seek(self.position())
            producer.set_speed(self.producer.get_speed())
        producer.set("eof", "loop")
        self.producer = producer
        self.consumer.disconnect_all_producers()
        self.consumer.connect(self.producer)

class Timeline:

    """
    >>> cut = Source("hello").create_cut(0, 10)
    >>> timeline = Timeline()
    >>> timeline.add(cut)
    >>> width, height = 300, 100
    >>> surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
    >>> context = cairo.Context(surface)
    >>> timeline.draw_cairo(
    ...     context=context,
    ...     playhead_position=0,
    ...     width=width,
    ...     height=height
    ... )
    >>> timeline.rectangle_map
    Rectangle(x=10, y=10, width=10, height=80):
      Cut(source=Source(name='hello'), in_out=Region(start=0, end=10), position=0)
    >>> timeline.split_into_sections().to_ascii_canvas()
    |<-h0----->|
    >>> timeline.mouse_down(15, 15)
    >>> timeline.mouse_move(16, 16)
    >>> timeline.mouse_up()
    >>> timeline.split_into_sections().to_ascii_canvas()
    |%<-h0----->|
    >>> timeline.mouse_move(17, 17)
    >>> timeline.split_into_sections().to_ascii_canvas()
    |%<-h0----->|
    """

    @staticmethod
    def with_test_clips():
        timeline = Timeline()
        timeline.add(Source("resources/one-to-five.mp4").create_cut(0, 5).move(0))
        timeline.add(Source("resources/one.mp4").create_cut(0, 15).move(10))
        timeline.add(Source("resources/two.mp4").create_cut(0, 15).move(20))
        timeline.add(Source("resources/three.mp4").create_cut(0, 15).move(30))
        timeline.set_zoom_factor(25)
        return timeline

    def __init__(self):
        self.cuts = Cuts()
        self.zoom_factor = 1
        self.rectangle_map = RectangleMap()
        self.mouse_up()

    def mouse_down(self, x, y):
        self.tmp_xy = (x, y)
        self.tmp_cuts = self.cuts
        self.tmp_cut = self.rectangle_map.get(x, y)

    def mouse_move(self, x, y):
        if self.tmp_cut:
            delta = x-self.tmp_xy[0]
            self.cuts = self.tmp_cuts.modify(self.tmp_cut, lambda x:
                x.move(int(delta/self.zoom_factor)))

    def mouse_up(self):
        self.tmp_xy = None
        self.tmp_cuts = None
        self.tmp_cut = None

    def add(self, cut):
        self.cuts = self.cuts.add(cut)

    def set_zoom_factor(self, zoom_factor):
        # TODO: allow zoom factor to be set with mouse wheel
        self.zoom_factor = zoom_factor

    def split_into_sections(self):
        return self.cuts.split_into_sections()

    def to_mlt_producer(self, profile):
        return self.split_into_sections().to_mlt_producer(profile)

    def draw_cairo(self, context, playhead_position, width, height):
        """
        >>> width, height = 300, 100
        >>> surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
        >>> context = cairo.Context(surface)
        >>> timeline = Timeline()
        >>> timeline.add(Source("hello").create_cut(0, 10).move(0))
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
        >>> timeline.rectangle_map
        Rectangle(x=10, y=10, width=10, height=80):
          Cut(source=Source(name='hello'), in_out=Region(start=0, end=10), position=0)
        """
        self.rectangle_map.clear()
        offset = 10
        context.save()
        context.translate(offset, offset)
        self.split_into_sections().draw_cairo(
            context=context,
            height=height-2*offset,
            x_factor=self.zoom_factor,
            rectangle_map=self.rectangle_map
        )
        context.set_source_rgb(0.1, 0.1, 0.1)
        context.move_to(playhead_position*self.zoom_factor, -10)
        context.line_to(playhead_position*self.zoom_factor, height-10)
        context.stroke()
        context.restore()

if __name__ == "__main__":
    App().run()
