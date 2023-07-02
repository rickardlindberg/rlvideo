class AsciiCanvas:

    def __init__(self):
        self.chars = {}

    def get_max_x(self):
        return max(x for (x, y) in self.chars.keys())

    def get_max_y(self):
        return max(y for (x, y) in self.chars.keys())

    def add_text(self, text, x, y):
        for index, char in enumerate(text):
            self.add_char(x+index, y, char)

    def add_canvas(self, canvas, dx=0, dy=0):
        for (x, y), value in canvas.chars.items():
            self.add_char(x+dx, y+dy, value)

    def add_char(self, x, y, char):
        """
        >>> AsciiCanvas().add_char(-1, 5, 'h')
        Traceback (most recent call last):
          ...
        ValueError: Invalid ascii char 'h' at (-1, 5): position is outside grid.

        >>> AsciiCanvas().add_char(0, 0, 'hello')
        Traceback (most recent call last):
          ...
        ValueError: Invalid ascii char 'hello' at (0, 0): length is not 1.
        """
        if x < 0 or y < 0:
            raise ValueError(f"Invalid ascii char {char!r} at ({x}, {y}): position is outside grid.")
        if len(char) != 1:
            raise ValueError(f"Invalid ascii char {char!r} at ({x}, {y}): length is not 1.")
        self.chars[(x, y)] = char

    def __repr__(self):
        lines = []
        if self.chars:
            max_y = max(y for (x, y) in self.chars.keys())
            for y in range(max_y+1):
                chars_for_y = {}
                for (x2, y2), char in self.chars.items():
                    if y2 == y:
                        chars_for_y[x2] = char
                if chars_for_y:
                    max_x = max(x for x in chars_for_y.keys())
                    lines.append("".join([
                        chars_for_y.get(x, " ")
                        for x in range(max_x+1)
                    ]))
                else:
                    lines.append("")
        return "\n".join(lines)
