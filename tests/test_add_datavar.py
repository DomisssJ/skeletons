from geo_skeletons import PointSkeleton
from geo_skeletons.decorators import add_datavar, add_coord
import numpy as np


def test_add_datavar():
    points = PointSkeleton(x=0, y=4)
    points.add_datavar("hs")

    assert "hs" in points.data_vars()
    assert "hs" in list(points.ds().keys())


def test_add_datavar_on_top():
    @add_datavar(name="hs")
    @add_coord(name="z")
    class Expanded(PointSkeleton):
        pass

    assert "hs" in list(Expanded._coord_manager.added_vars().keys())

    points = Expanded(x=[6, 7, 8], y=[4, 5, 6], z=[6, 7])
    points.add_datavar("tp", default_value=5.0, coords="gridpoint")
    assert "hs" in points.data_vars()
    assert "hs" in list(points.ds().keys())
    assert "tp" in points.data_vars()
    assert "tp" in list(points.ds().keys())

    np.testing.assert_almost_equal(np.mean(points.tp()), 5.0)

    assert points.size("gridpoint") == points.tp().shape