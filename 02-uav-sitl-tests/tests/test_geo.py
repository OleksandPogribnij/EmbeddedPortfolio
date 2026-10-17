"""Unit tests for geographic helpers; no simulator needed (UT-001..UT-003)."""

import pytest

from utils.geo import distance_m


class TestGeo:
    """Distance calculation on the Earth's surface."""

    def test_same_point(self):
        """UT-001: distance between identical points is zero."""
        point_lat = 0.0
        point_lon = 0.0

        distance = distance_m(point_lat, point_lon, point_lat, point_lon)
        assert distance == 0.0, f"Distance between identical points: expected 0 m, got {distance} m"

    def test_distance_along_latitude(self):
        """UT-002: 0.001 deg of latitude is about 111 m."""
        cur_point_lat = 0.0
        cur_point_lon = 0.0

        new_point_lat = 0.001
        new_point_lon = cur_point_lon

        distance = distance_m(cur_point_lat, cur_point_lon, new_point_lat, new_point_lon)
        assert distance == pytest.approx(111, abs=1), (
            f"Distance for 0.001 deg of latitude: expected 111 +/- 1 m, got {distance:.2f} m"
        )

    def test_distance_along_longitude(self):
        """UT-003: 0.001 deg of longitude at 49 deg N is about 73 m."""
        cur_point_lat = 49.0
        cur_point_lon = 24.0

        new_point_lat = cur_point_lat
        new_point_lon = 24.001

        distance = distance_m(cur_point_lat, cur_point_lon, new_point_lat, new_point_lon)
        assert distance == pytest.approx(73, abs=1), (
            f"Distance for 0.001 deg of longitude at 49 deg N: "
            f"expected 73 +/- 1 m, got {distance:.2f} m"
        )
