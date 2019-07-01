from testing.test import Test


class PassTest(Test):
    """A dummy test suite that always passes."""
    def __init__(self, **kwargs):
        pass

    def run_tests(self, **kwargs):
        return (1, 0)


class FailTest(Test):
    """A dummy test suite that always fails."""
    def __init__(self, **kwargs):
        pass

    def run_tests(self, **kwargs):
        return (0, 1)
