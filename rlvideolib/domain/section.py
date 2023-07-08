import mlt

from rlvideolib.asciicanvas import AsciiCanvas
from rlvideolib.graphics.rectangle import Rectangle

class Sections:

    def __init__(self):
        self.sections = []

    @property
    def length(self):
        return sum(section.length for section in self.sections)

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

    def draw_cairo(self, context, rectangle, rectangle_map):
        context.save()
        for section in self.sections:
            r = Rectangle.from_size(
                width=(section.length/self.length)*rectangle.width,
                height=rectangle.height
            )
            section.draw_cairo(
                context=context,
                rectangle=r,
                rectangle_map=rectangle_map,
            )
            context.translate(r.width, 0)
        context.restore()

class PlaylistSection:

    def __init__(self, length, parts):
        assert length == sum(part.length for part in parts)
        self.length = length
        self.parts = parts

    def to_ascii_canvas(self):
        canvas = AsciiCanvas()
        x = 0
        for part in self.parts:
            canvas.add_canvas(part.to_ascii_canvas(), dx=x)
            x = canvas.get_max_x() + 1
        return canvas

    def to_mlt_producer(self, profile):
        playlist = mlt.Playlist()
        for part in self.parts:
            part.add_to_mlt_playlist(profile, playlist)
        assert playlist.get_playtime() == self.length
        return playlist

    def draw_cairo(self, context, rectangle, rectangle_map):
        context.save()
        for part in self.parts:
            r = Rectangle.from_size(
                width=(part.length/self.length)*rectangle.width,
                height=rectangle.height
            )
            part.draw_cairo(context, r, rectangle_map)
            context.translate(r.width, 0)
        context.restore()

class MixSection:

    def __init__(self, length, playlists):
        for playlist in playlists:
            assert playlist.length == length
        self.length = length
        self.playlists = playlists

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
        assert tractor.get_playtime() == self.length
        return tractor

    def draw_cairo(self, context, rectangle, rectangle_map):
        """
        >>> import cairo
        >>> from rlvideolib.graphics.rectangle import RectangleMap
        >>> from rlvideolib.domain.cut import Cut

        >>> rectangle = Rectangle.from_size(width=300, height=100)
        >>> surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, rectangle.width, rectangle.height)
        >>> context = cairo.Context(surface)

        >>> rectangle_map = RectangleMap()
        >>> MixSection(
        ...     length=0,
        ...     playlists=[]
        ... ).draw_cairo(context, rectangle, rectangle_map)
        >>> rectangle_map
        <BLANKLINE>

        >>> rectangle_map = RectangleMap()
        >>> MixSection(
        ...     length=6,
        ...     playlists=[
        ...         PlaylistSection(
        ...             length=6,
        ...             parts=[
        ...                 Cut.test_instance(name="A", start=0, end=6, position=0),
        ...             ]
        ...         ),
        ...         PlaylistSection(
        ...             length=6,
        ...             parts=[
        ...                 Cut.test_instance(name="B", start=0, end=6, position=0),
        ...             ]
        ...         ),
        ...     ]
        ... ).draw_cairo(context, rectangle, rectangle_map)
        >>> rectangle_map
        Rectangle(x=0, y=0, width=300, height=50):
          Cut(source=Source(name='A'), in_out=Region(start=0, end=6), position=0)
        Rectangle(x=0, y=50, width=300, height=50):
          Cut(source=Source(name='B'), in_out=Region(start=0, end=6), position=0)
        """
        if not self.playlists:
            return
        sub_height = rectangle.height // len(self.playlists)
        rest = rectangle.height % len(self.playlists)
        r = rectangle
        for index, playlist in enumerate(self.playlists):
            if rest:
                rest -= 1
                h = sub_height + 1
            else:
                h = sub_height
            r = r._replace(height=h)
            with r.cairo_clip_translate(context) as re:
                playlist.draw_cairo(context, re, rectangle_map)
            r = r.move(dy=h)
