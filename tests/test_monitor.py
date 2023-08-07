# the inclusion of the tests module is not meant to offer best practices for
# testing in general, but rather to support the `find_packages` example in
# setup.py that excludes installing the "tests" package

import unittest

from zelus.core import Zelus, Mode
import time


class TestMonitor(unittest.TestCase):

    def test_monitor(self):
        z = Zelus(
            mode=Mode.MONITOR,
            monitored_interfaces=['wlo1'],
            monitored_tables=['main']
        )

        h = z.monitor()

        time.sleep(1)

        z.stop.set()

        h.join()


if __name__ == '__main__':
    unittest.main()
