from ..gridded_skeleton import GriddedSkeleton
from ..coordinate_factory import add_coord
from ..datavar_factory import add_datavar
import numpy as np


def test_add_datavar():
    @add_datavar(name="hs", default_value=0.0)
    class WaveHeight(GriddedSkeleton):
        pass

    data = WaveHeight(lon=(10, 20), lat=(30, 40))
    data.set_spacing(nx=10, ny=10)
    assert np.mean(data.hs()) == 0
    data.set_hs(1)
    assert np.mean(data.hs()) == 1
    data.set_hs(1.0)
    assert np.mean(data.hs()) == 1.0
    data.set_hs(np.full(data.size(), 2.0))
    assert np.mean(data.hs()) == 2.0


def test_add_coord_and_datavar():
    @add_datavar(name="hs", default_value=0.0)
    @add_coord(name="z", grid_coord=True)
    class WaveHeight(GriddedSkeleton):
        pass

    data = WaveHeight(lon=(10, 20), lat=(30, 40), z=(1, 3))
    data.set_spacing(nx=10, ny=10)
    data.set_z_spacing(nx=3)
    assert np.mean(data.hs()) == 0
    data.set_hs(1)
    assert np.mean(data.hs()) == 1
    data.set_hs(1.0)
    assert np.mean(data.hs()) == 1.0
    data.set_hs(np.full(data.size(), 2.0))
    assert np.mean(data.hs()) == 2.0