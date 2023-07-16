class Event:

    """
    >>> def listener():
    ...     print("got event")
    >>> event = Event()
    >>> event.trigger()
    >>> event.listen(listener)
    >>> event.trigger()
    got event
    """

    def __init__(self):
        self.listeners = []

    def trigger(self):
        for fn in self.listeners:
            fn()

    def listen(self, fn):
        self.listeners.append(fn)
