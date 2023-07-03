from collections import namedtuple
from rlvideolib.asciicanvas import AsciiCanvas
from rlvideolib.domain.region import Region
from rlvideolib.domain.region import Regions
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
                print("Seek 0")
                producer.seek(0)
                consumer.purge()

        main_window = Gtk.Window()
        main_window.connect("destroy", Gtk.main_quit)
        main_window.connect("key_press_event", key_press_handler)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        main_window.add(box)

        preview = Gtk.DrawingArea()
        box.pack_start(preview, True, True, 0)

        def timeline_draw(widget, context):
            self.timeline.draw(
                widget.get_allocated_width(),
                widget.get_allocated_height(),
                context,
                producer.position()
            )
        timeline = Gtk.DrawingArea()
        timeline.connect("draw", timeline_draw)
        def redraw():
            timeline.queue_draw()
            return True
        refresh_id = GLib.timeout_add(100, redraw)
        box.pack_start(timeline, True, True, 0)

        main_window.show_all()

        os.putenv("SDL_WINDOWID", str(preview.get_window().get_xid()))
        producer = self.generate_mlt_producer()
        producer.set("eof", "loop")
        consumer = mlt.Consumer(self.profile, "sdl")
        consumer.connect(producer)
        consumer.start()

        Gtk.main()

class Timeline:

    @staticmethod
    def with_test_clips():
        timeline = Timeline()
        timeline.add(Source("hello").create_cut(0, 75).at(0))
        timeline.add(Source("video").create_cut(0, 75).at(50))
        timeline.add(Source("world").create_cut(0, 75).at(100))
        return timeline

    def __init__(self):
        self.cuts = Cuts()

    def add(self, cut):
        self.cuts.append(cut)

    def to_mlt_producer(self, profile):
        return self.cuts.flatten().to_mlt_producer(profile)

    def draw(self, width, height, context, position):
        context.set_source_rgb(1, 0, 0)
        context.rectangle(position, 10, 10, 10)
        context.fill()

class Source(namedtuple("Source", "name")):

    def create_cut(self, start, end):
        return Cut.create(
            source=self,
            in_out=Region(start=start, end=end)
        )

    def to_mlt_producer(self, profile):
        producer = mlt.Producer(profile, "pango")
        producer.set("text", self.name)
        producer.set("bgcolour", "red")
        return producer

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

    def to_ascii_canvas(self):
        """
        >>> Source("A").create_cut(0, 4).to_ascii_canvas()
        A0->
        """
        canvas = AsciiCanvas()
        text = self.source.name[0]+str(self.in_out.start)
        text = text+"-"*(self.length-len(text)-1)
        text = text+">"
        if len(text) != self.length:
            raise ValueError(f"Could not represent cut {self} as ascii.")
        canvas.add_text(text, self.start, 0)
        return canvas

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

    def cut_region(self, region):
        """
        >>> cut = Cut(source=Source("A"), in_out=Region(start=10, end=20), position=2)
        >>> cut.cut_region(Region(start=5, end=10))
        Cut(source=Source(name='A'), in_out=Region(start=13, end=18), position=5)
        """
        overlap = self.region.get_overlap(region)
        if overlap:
            new_start = self.in_out.start+overlap.start-self.position
            return self._replace(
                position=overlap.start,
                in_out=Region(
                    start=new_start,
                    end=new_start+overlap.length,
                )
            )
        else:
            return None

    def to_mlt_producer(self, profile):
        return self.source.to_mlt_producer(profile).cut(
            self.in_out.start,
            self.in_out.end-1
        )

class Cuts(list):

    def flatten(self):
        """
        A single cut returns a single section with that cut:

        >>> Cuts([
        ...     Source(name="A").create_cut(0, 10).at(0)
        ... ]).flatten().to_ascii_canvas()
        |A0------->|

        Two non-overlapping cuts returns two sections with each cut in each:

        >>> Cuts([
        ...     Source(name="A").create_cut(0, 10).at(0),
        ...     Source(name="B").create_cut(0, 10).at(10),
        ... ]).flatten().to_ascii_canvas()
        |A0------->|B0------->|

        Overlap:

        >>> Cuts([
        ...     Source(name="A").create_cut(0, 10).at(0),
        ...     Source(name="B").create_cut(0, 10).at(5),
        ... ]).flatten().to_ascii_canvas()
        |A0-->|A5-->|B5-->|
        |     |B0-->|     |

        No cuts:

        >>> Cuts().flatten()
        Sections([])
        """
        sections = Sections()
        start = self.start
        for overlap in self.get_regions_with_overlap():
            for cut in self.cut_region(Region(start=start, end=overlap.start)):
                sections.add(Cuts([cut]))
            sections.add(self.cut_region(overlap))
            start = overlap.end
        for cut in self.cut_region(Region(start=start, end=self.end)):
            sections.add(Cuts([cut]))
        return sections

    def get_regions_with_overlap(self):
        overlaps = Regions()
        cuts = list(self)
        while cuts:
            cut = cuts.pop(0)
            for other in cuts:
                overlap = cut.get_overlap(other)
                if overlap:
                    overlaps.add(overlap)
        return overlaps.merge()

    def cut_region(self, region):
        cuts = Cuts()
        for cut in self:
            sub_cut = cut.cut_region(region)
            if sub_cut:
                cuts.append(sub_cut)
        return cuts

    @property
    def start(self):
        """
        >>> Cuts().start
        0

        >>> Cuts([Source("A").create_cut(0, 5).at(5)]).start
        5
        """
        if self:
            return min(cut.region.start for cut in self)
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
        if self:
            return max(cut.region.end for cut in self)
        else:
            return 0

class Sections:

    def __init__(self):
        self.sections = []

    def add(self, *cuts):
        for cut in cuts:
            self.sections.append(Section(cut))

    def to_ascii_canvas(self):
        canvas = AsciiCanvas()
        offset = 1
        lines = [0]
        for section in self.sections:
            canvas.add_canvas(section.to_ascii_canvas(), dx=offset)
            lines.append(canvas.get_max_x()+1)
            offset += 1
        for line in lines:
            for y in range(canvas.get_max_y()+1):
                canvas.add_text("|", line, y)
        return canvas

    def to_mlt_producer(self, profile):
        playlist = mlt.Playlist()
        for section in self.sections:
            playlist.append(section.to_mlt_producer(profile))
        return playlist

    def __repr__(self):
        return f"Sections({self.sections})"

class Section:

    def __init__(self, cuts):
        self.cuts = cuts

    def to_ascii_canvas(self):
        canvas = AsciiCanvas()
        for y, cut in enumerate(self.cuts):
            canvas.add_canvas(cut.to_ascii_canvas(), dy=y)
        return canvas

    def to_mlt_producer(self, profile):
        if len(self.cuts) == 1:
            return self.cuts[0].to_mlt_producer(profile)
        elif len(self.cuts) == 2:
            a, b = self.cuts
            tractor = mlt.Tractor()
            tractor.insert_track(a.to_mlt_producer(profile), 0)
            tractor.insert_track(b.to_mlt_producer(profile), 1)
            transition = mlt.Transition(profile, "luma")
            tractor.plant_transition(transition, 0, 1)
            return tractor
        else:
            raise ValueError("Only 1 and 2 tracks supported.")

if __name__ == "__main__":
    App().run()
