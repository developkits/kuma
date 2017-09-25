from functools import wraps

import pytest


skip_if_maintenance_mode = pytest.mark.skipif(
    pytest.config.getoption('--maintenance-mode'),
    reason='the server is in maintenance mode'
)


skip_if_not_maintenance_mode = pytest.mark.skipif(
    not pytest.config.getoption('--maintenance-mode'),
    reason='the server is not in maintenance mode'
)


def wait_for_window(page_attr=None):
    """
    Wait for the tab or window opend by the action.

    Firefox will sometimes return from click methods before the tab
    or window is fully opened. Chrome waits for the new window.
    """
    def wrap(fn):
        @wraps(fn)
        def wrapped_fn(self=None, *args, **kwargs):
            if page_attr:
                page = getattr(self, page_attr)
            else:
                page = self
            window_count = len(page.selenium.window_handles)
            fn(self, *args, **kwargs)
            self.wait.until(lambda s: len(s.window_handles) > window_count)

        return wrapped_fn
    return wrap
