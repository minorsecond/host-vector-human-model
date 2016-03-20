"""
unit tests
"""

import unittest
from simulation import point_in_poly

class testPointInPolygon(unittest.TestCase):


    def test_inside(self):
        polygon = [(0, 10), (10, 10), (10, 0), (0, 0)]

        point_x = 5
        point_y = 5

        self.assertTrue(point_in_poly(point_x, point_y, polygon))

    def test_outside(self):
        polygon = [(0, 10), (10, 10), (10, 0), (0, 0)]

        point_x = 1
        point_y = 5

        self.assertFalse(point_in_poly(point_x, point_y, polygon))


if __name__ == '__main__':
    unittest.main()