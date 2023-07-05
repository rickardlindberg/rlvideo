from collections import namedtuple

class Rectangle(namedtuple("Rectangle", "x,y,width,height")):

    def contains(self, x, y):
        if x < self.x:
            return False
        elif x > self.x+self.width:
            return False
        elif y < self.y:
            return False
        elif y > self.y+self.height:
            return False
        else:
            return True

class RectangleMap:

    """
    >>> r = RectangleMap()
    >>> r.add(Rectangle(x=0, y=0, width=10, height=10), "item")
    >>> r.get(5, 5)
    'item'
    >>> r.get(100, 100) is None
    True
    """

    def __init__(self):
        self.map = []

    def clear(self):
        self.map.clear()

    def add(self, rectangle, item):
        self.map.append((rectangle, item))

    def get(self, x, y):
        for rectangle, item in self.map:
            if rectangle.contains(x, y):
                return item

    def __repr__(self):
        return "\n".join(f"{rectangle}:\n  {item}" for rectangle, item in self.map)
