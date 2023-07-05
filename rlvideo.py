from collections import namedtuple
from rlvideolib.asciicanvas import AsciiCanvas
from rlvideolib.domain.region import Region
from rlvideolib.domain.region import Regions
from rlvideolib.domain.source import Source
from rlvideolib.graphics.rectangle import RectangleMap
from rlvideolib.graphics.rectangle import Rectangle
import cairo
import os
import mlt
import time
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib

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
            self.timeline.draw(
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
    >>> timeline.draw(
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
        timeline.add(Source("resources/one-to-five.mp4").create_cut(0, 5).at(0))
        timeline.add(Source("resources/one.mp4").create_cut(0, 15).at(10))
        timeline.add(Source("resources/two.mp4").create_cut(0, 15).at(20))
        timeline.add(Source("resources/three.mp4").create_cut(0, 15).at(30))
        timeline.set_zoom_factor(50)
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
        self.zoom_factor = zoom_factor

    def split_into_sections(self):
        return self.cuts.split_into_sections()

    def to_mlt_producer(self, profile):
        return self.split_into_sections().to_mlt_producer(profile)

    def draw(self, context, playhead_position, width, height):
        """
        >>> width, height = 300, 100
        >>> surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
        >>> context = cairo.Context(surface)
        >>> timeline = Timeline()
        >>> timeline.add(Source("hello").create_cut(0, 10).at(0))
        >>> timeline.draw(
        ...     context=context,
        ...     playhead_position=0,
        ...     width=width,
        ...     height=height
        ... )
        >>> timeline.draw(
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
        self.split_into_sections().draw(
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

class Cut(namedtuple("Cut", "source,in_out,position")):

    @staticmethod
    def create(source, in_out, position=0):
        return Cut(source=source, in_out=in_out, position=position)

    @property
    def length(self):
        return self.in_out.length

    @property
    def start(self):
        return self.position

    @property
    def end(self):
        return self.position+self.length

    def move(self, delta):
        """
        >>> Cut(source=None, in_out=None, position=5).move(-10).position
        0
        """
        return self._replace(position=max(0, self.position+delta))

    @property
    def region(self):
        """
        >>> Cut(source=Source("B"), in_out=Region(start=10, end=20), position=10).region
        Region(start=10, end=20)
        """
        return Region(start=self.position, end=self.position+self.length)

    def at(self, position):
        """
        >>> Cut.create(source=Source("A"), in_out=Region(start=0, end=10)).at(10)
        Cut(source=Source(name='A'), in_out=Region(start=0, end=10), position=10)
        """
        return self._replace(position=position)

    def get_overlap(self, cut):
        """
        >>> a = Cut(source=Source("A"), in_out=Region(start=10, end=20), position=5)
        >>> b = Cut(source=Source("B"), in_out=Region(start=10, end=20), position=10)
        >>> a.get_overlap(b)
        Region(start=10, end=15)
        """
        return self.region.get_overlap(cut.region)

    def starts_at_original_cut(self):
        """
        >>> cut = Source("A").create_cut(0, 10).at(0)
        >>> cut.starts_at_original_cut()
        True
        >>> cut.create_cut(Region(start=5, end=6)).starts_at_original_cut()
        False
        """
        return self.source.starts_at(self.start)

    def starts_at(self, position):
        return self.start == position

    def ends_at_original_cut(self):
        """
        >>> cut = Source("A").create_cut(0, 10).at(0)
        >>> cut.ends_at_original_cut()
        True
        >>> cut.create_cut(Region(start=5, end=6)).ends_at_original_cut()
        False
        """
        return self.source.ends_at(self.end)

    def ends_at(self, position):
        return self.end == position

    def create_cut(self, region):
        """
        >>> cut = Source("A").create_cut(0, 20).at(10)
        >>> cut
        Cut(source=Source(name='A'), in_out=Region(start=0, end=20), position=10)

        Contains all:

        >>> cut.create_cut(Region(start=0, end=40))
        Cut(source=Source(name='A'), in_out=Region(start=0, end=20), position=10)

        >>> cut.create_cut(Region(start=10, end=30))
        Cut(source=Source(name='A'), in_out=Region(start=0, end=20), position=10)

        Subcut left:

        >>> sub = cut.create_cut(Region(start=15, end=30))
        >>> sub.source is cut
        True
        >>> sub.in_out
        Region(start=5, end=20)
        >>> sub.position
        15

        No overlap:

        >>> cut.create_cut(Region(start=0, end=10)) is None
        True
        """
        overlap = self.region.get_overlap(region)
        if overlap:
            if overlap.start == self.start and overlap.end == self.end:
                return self
            else:
                return self._replace(
                    source=self,
                    in_out=Region(
                        start=overlap.start-self.start,
                        end=overlap.start-self.start+overlap.length
                    ),
                    position=overlap.start
                )
        else:
            return None

    def to_mlt_producer(self, profile):
        return self.source.to_mlt_producer(profile).cut(
            self.in_out.start,
            self.in_out.end-1
        )

    def add_to_mlt_playlist(self, profile, playlist):
        playlist.append(self.to_mlt_producer(profile))

    def to_ascii_canvas(self):
        """
        >>> cut = Source("A").create_cut(0, 10).at(0)

        >>> cut.to_ascii_canvas()
        <-A0----->

        >>> cut.create_cut(Region(start=1, end=9)).to_ascii_canvas()
        -A1-----

        >>> Source("A").create_cut(0, 6).at(0).to_ascii_canvas()
        <-A0->

        >>> Source("A").create_cut(0, 5).at(0).to_ascii_canvas()
        #####
        """
        if self.starts_at_original_cut():
            start_marker = "<-"
        else:
            start_marker = "-"
        if self.ends_at_original_cut():
            end_marker = "->"
        else:
            end_marker = "-"
        text = ""
        text += start_marker
        text += self.get_label()[0]
        text += str(self.in_out.start)
        text += "-"*(self.length-len(text)-len(end_marker))
        text += end_marker
        if len(text) != self.length:
            text = "#"*self.length
        canvas = AsciiCanvas()
        canvas.add_text(text, 0, 0)
        return canvas

    def get_label(self):
        return self.source.get_label()

    def get_source_cut(self):
        if isinstance(self.source, Cut):
            return self.source.get_source_cut()
        else:
            return self

    def draw(self, context, height, x_factor, rectangle_map):
        y = 0
        x = self.start * x_factor
        w = self.length * x_factor
        h = height

        rect_x, rect_y = context.user_to_device(x, y)
        rect_w, rect_h = context.user_to_device_distance(w, h)
        rectangle_map.add(Rectangle(
            x=int(rect_x),
            y=int(rect_y),
            width=int(rect_w),
            height=int(rect_h)
        ), self.get_source_cut())

        context.set_source_rgb(1, 0, 0)
        context.rectangle(x, y, w, h)
        context.fill()

        context.set_source_rgb(0, 0, 0)

        context.move_to(x, y)
        context.line_to(x+w, y)
        context.stroke()

        context.move_to(x, y+height)
        context.line_to(x+w, y+height)
        context.stroke()

        if self.starts_at_original_cut():
            context.set_source_rgb(0, 0, 0)
            context.move_to(x, y)
            context.line_to(x, y+height)
            context.stroke()

        if self.ends_at_original_cut():
            context.set_source_rgb(0, 0, 0)
            context.move_to(x+w, y)
            context.line_to(x+w, y+height)
            context.stroke()

        if self.starts_at_original_cut():
            context.move_to(x+2, y+10)
            context.set_source_rgb(0, 0, 0)
            context.text_path(self.get_label())
            context.fill()

class Cuts:

    """
    >>> a = Source("A").create_cut(0, 20).at(0)
    >>> b = Source("b").create_cut(0, 20).at(10)
    >>> cuts = Cuts()
    >>> cuts = cuts.add(a)
    >>> cuts = cuts.add(b)
    >>> cuts.split_into_sections().to_ascii_canvas()
    |<-A0------|-A10----->|-b10----->|
    |          |<-b0------|          |
    >>> cuts.modify(b, lambda cut: cut.move(1)).split_into_sections().to_ascii_canvas()
    |<-A0-------|-A11---->|-b9------->|
    |           |<-b0-----|           |
    """

    def __init__(self, cuts=[]):
        self.cuts = list(cuts)

    def add(self, cut):
        return Cuts(self.cuts+[cut])

    def modify(self, cut_to_modify, fn):
        return Cuts([
            fn(cut) if cut is cut_to_modify else cut
            for cut in self.cuts
        ])

    def create_cut(self, period):
        """
        >>> cuts = Cuts([
        ...     Source(name="A").create_cut(0, 8).at(0),
        ...     Source(name="B").create_cut(0, 8).at(5),
        ... ])
        >>> cuts.to_ascii_canvas()
        |<-A0--->     |
        |     <-B0--->|
        >>> cuts.create_cut(Region(start=2, end=13)).to_ascii_canvas()
        |  -A2-->     |
        |     <-B0--->|
        """
        cuts = []
        for cut in self.cuts:
            sub_cut = cut.create_cut(period)
            if sub_cut:
                cuts.append(sub_cut)
        return Cuts(cuts)

    def split_into_sections(self):
        """
        A single cut returns a single section with that cut:

        >>> Cuts([
        ...     Source(name="A").create_cut(0, 10).at(0)
        ... ]).split_into_sections().to_ascii_canvas()
        |<-A0----->|

        Two non-overlapping cuts returns two sections with each cut in each:

        >>> Cuts([
        ...     Source(name="A").create_cut(0, 10).at(0),
        ...     Source(name="B").create_cut(0, 10).at(10),
        ... ]).split_into_sections().to_ascii_canvas()
        |<-A0-----><-B0----->|

        Overlap:

        >>> Cuts([
        ...     Source(name="A").create_cut(0, 20).at(0),
        ...     Source(name="B").create_cut(0, 20).at(10),
        ... ]).split_into_sections().to_ascii_canvas()
        |<-A0------|-A10----->|-B10----->|
        |          |<-B0------|          |

        No cuts:

        >>> Cuts().split_into_sections().to_ascii_canvas()
        <BLANKLINE>

        Initial space:

        >>> Cuts([
        ...     Source(name="A").create_cut(0, 10).at(5)
        ... ]).split_into_sections().to_ascii_canvas()
        |%%%%%<-A0----->|

        BUG:

        >>> Cuts([
        ...     Source(name="A").create_cut(0, 10).at(5),
        ...     Source(name="B").create_cut(0, 10).at(5),
        ... ]).split_into_sections().to_ascii_canvas()
        |%%%%%|<-A0----->|
        |     |<-B0----->|

        BUG:

        >>> cuts = Cuts([
        ...     Source(name="A").create_cut(0, 20).at(30),
        ...     Source(name="B").create_cut(0, 20).at(0),
        ...     Source(name="C").create_cut(0, 20).at(10),
        ... ])
        >>> cuts.split_into_sections().to_ascii_canvas()
        |<-B0------|-B10----->|-C10-----><-A0--------------->|
        |          |<-C0------|                              |
        """
        sections = Sections()
        start = 0
        for overlap in self.get_regions_with_overlap():
            if overlap.start > start:
                sections.add(self.extract_playlist_section(Region(
                    start=start,
                    end=overlap.start
                )))
            sections.add(self.extract_mix_section(overlap))
            start = overlap.end
        if self.end > start:
            sections.add(self.extract_playlist_section(Region(
                start=start,
                end=self.end
            )))
        return sections

    def extract_playlist_section(self, region):
        """
        >>> cuts = Cuts([
        ...     Source(name="A").create_cut(0, 8).at(1),
        ...     Source(name="B").create_cut(0, 8).at(10),
        ... ])
        >>> cuts.to_ascii_canvas()
        | <-A0--->         |
        |          <-B0--->|
        >>> cuts.extract_playlist_section(Region(start=0, end=20)).to_ascii_canvas()
        %<-A0--->%<-B0--->%%
        """
        return PlaylistSection(region=region, cuts=self.create_cut(region))

    def extract_mix_section(self, region):
        """
        >>> cuts = Cuts([
        ...     Source(name="A").create_cut(0, 8).at(1),
        ...     Source(name="B").create_cut(0, 8).at(5),
        ... ])
        >>> cuts.to_ascii_canvas()
        | <-A0--->    |
        |     <-B0--->|
        >>> cuts.extract_mix_section(Region(start=0, end=15)).to_ascii_canvas()
        %<-A0--->%%%%%%
        %%%%%<-B0--->%%
        """
        return MixSection(region=region, cuts=self.create_cut(region))

    def get_regions_with_overlap(self):
        overlaps = Regions()
        cuts = list(self.cuts)
        while cuts:
            cut = cuts.pop(0)
            for other in cuts:
                overlap = cut.get_overlap(other)
                if overlap:
                    overlaps.add(overlap)
        return overlaps.merge()

    @property
    def start(self):
        """
        >>> Cuts().start
        0

        >>> Cuts([Source("A").create_cut(0, 5).at(5)]).start
        5
        """
        if self.cuts:
            return min(cut.start for cut in self.cuts)
        else:
            return 0

    @property
    def end(self):
        """
        >>> Cuts().end
        0

        >>> Cuts([Source("A").create_cut(0, 5).at(5)]).end
        10
        """
        if self.cuts:
            return max(cut.end for cut in self.cuts)
        else:
            return 0

    def to_ascii_canvas(self):
        """
        >>> Cuts([
        ...     Source(name="A").create_cut(0, 8).at(10),
        ...     Source(name="B").create_cut(0, 8).at(0),
        ...     Source(name="C").create_cut(0, 8).at(5),
        ... ]).to_ascii_canvas()
        |          <-A0--->|
        |<-B0--->          |
        |     <-C0--->     |
        """
        canvas = AsciiCanvas()
        for y, cut in enumerate(self.cuts):
            canvas.add_canvas(cut.to_ascii_canvas(), dy=y, dx=cut.start+1)
        x = canvas.get_max_x()+1
        for y in range(len(self.cuts)):
            canvas.add_text("|", 0, y)
            canvas.add_text("|", x, y)
        return canvas

class Sections:

    def __init__(self):
        self.sections = []

    def add(self, *sections):
        self.sections.extend(sections)

    def to_ascii_canvas(self):
        canvas = AsciiCanvas()
        if self.sections:
            offset = 1
            lines = [0]
            for section in self.sections:
                canvas.add_canvas(section.to_ascii_canvas(), dx=offset)
                lines.append(canvas.get_max_x()+1)
                offset += 1
                offset += section.length
            for line in lines:
                for y in range(canvas.get_max_y()+1):
                    canvas.add_text("|", line, y)
        return canvas

    def to_mlt_producer(self, profile):
        playlist = mlt.Playlist()
        for section in self.sections:
            playlist.append(section.to_mlt_producer(profile))
        return playlist

    def draw(self, context, height, x_factor, rectangle_map):
        for section in self.sections:
            section.draw(
                context=context,
                height=height,
                x_factor=x_factor,
                rectangle_map=rectangle_map
            )

class PlaylistSection:

    def __init__(self, region, cuts):
        # TODO: test value errors
        self.parts = []
        self.length = region.length
        start = region.start
        for cut in sorted(cuts.cuts, key=lambda cut: cut.start):
            if cut.start > start:
                self.parts.append(SpaceCut(cut.start-start))
            elif cut.start < start:
                raise ValueError("Cut overlaps start")
            self.parts.append(cut)
            start = cut.end
        if region.end > start:
            self.parts.append(SpaceCut(region.end-start))
        elif region.end < start:
            raise ValueError("Cut overlaps end")

    def to_ascii_canvas(self):
        canvas = AsciiCanvas()
        x = 0
        for part in self.parts:
            canvas.add_canvas(part.to_ascii_canvas(), dx=x)
            x = canvas.get_max_x() + 1
        return canvas

    def draw(self, context, height, x_factor, rectangle_map):
        for part in self.parts:
            part.draw(context, height, x_factor, rectangle_map)

    def to_mlt_producer(self, profile):
        playlist = mlt.Playlist()
        for part in self.parts:
            part.add_to_mlt_playlist(profile, playlist)
        assert playlist.get_playtime() == self.length
        return playlist

class MixSection:

    def __init__(self, region, cuts):
        self.length = region.length
        self.playlists = []
        for cut in cuts.cuts:
            self.playlists.append(PlaylistSection(region, Cuts([cut])))

    def to_ascii_canvas(self):
        canvas = AsciiCanvas()
        for y, playlist in enumerate(self.playlists):
            canvas.add_canvas(playlist.to_ascii_canvas(), dy=y)
        return canvas

    def to_mlt_producer(self, profile):
        tractor = mlt.Tractor()
        for playlist in self.playlists:
            tractor.insert_track(
                playlist.to_mlt_producer(profile),
                0
            )
        for clip_index in reversed(range(len(self.playlists))):
            if clip_index > 0:
                transition = mlt.Transition(profile, "luma")
                # TODO: plant the transition only on the overlap
                transition.set("in", 0)
                transition.set("out", self.length-1)
                tractor.plant_transition(transition, clip_index, clip_index-1)
        assert tractor.get_playtime() == self.length
        return tractor

    def draw(self, context, height, x_factor, rectangle_map):
        sub_height = height // len(self.playlists)
        rest = height % len(self.playlists)
        context.save()
        for index, playlist in enumerate(self.playlists):
            if rest:
                rest -= 1
                h = sub_height + 1
            else:
                h = sub_height
            playlist.draw(context, h, x_factor, rectangle_map)
            context.translate(0, h)
        context.restore()

class SpaceCut(namedtuple("SpaceCut", "length")):

    def to_ascii_canvas(self):
        canvas = AsciiCanvas()
        canvas.add_text("%"*self.length, 0, 0)
        return canvas

    def add_to_mlt_playlist(self, profile, playlist):
        playlist.blank(self.length-1)

    def draw(self, context, height, x_factor, rectangle_map):
        pass

if __name__ == "__main__":
    App().run()
