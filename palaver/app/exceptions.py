class TerminateRun(Exception):
    def __init__(self, output, *args):
        self.output = output
        super().__init__(*args)


class TooManyCalls(Exception): ...