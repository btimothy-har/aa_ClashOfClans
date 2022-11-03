class TerminateProcessing(Exception):
    """Raise this exception when processing should be terminated."""
    def __init__(self, exc):
        self.message = exc.message
        super().__init__(self.message)

    def __str__(self):
        return f'{self.message}'

class InvalidTag(Exception):
    """Raise this when a Clash Tag is invalid."""
    def __init__(self,tag):
        self.message = f'The tag `{tag}` is invalid.'
        super().__init__(self.message)

    def __str__(self):
        return f'{self.message}'