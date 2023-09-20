from skeletons.skeleton import sanitize_input
from skeletons.skeleton import will_grid_be_spherical_or_cartesian as func
import numpy as np


def test_lon_lat_tuple():
    x, y = None, None
    lon, lat = (0.0, 1.0), (2.0, 3.0)
    is_initialized = False

    for is_gridded in [True, False]:
        x, y, lon, lat, __ = sanitize_input(x, y, lon, lat, is_gridded, is_initialized)

        native_x, native_y, xvec, yvec = func(lon=lon, lat=lat, x=x, y=y)
        assert native_x == "lon"
        assert native_y == "lat"
        assert np.all(xvec == np.array([0.0, 1.0]))
        assert np.all(yvec == np.array([2.0, 3.0]))


def test_lon_lat_tuple_none_tuple():
    x, y = (None, None), (None, None)
    lon, lat = (0.0, 1.0), (2.0, 3.0)
    is_initialized = False

    for is_gridded in [True, False]:
        x, y, lon, lat, __ = sanitize_input(x, y, lon, lat, is_gridded, is_initialized)

        native_x, native_y, xvec, yvec = func(lon=lon, lat=lat, x=x, y=y)
        assert native_x == "lon"
        assert native_y == "lat"
        assert np.all(xvec == np.array([0.0, 1.0]))
        assert np.all(yvec == np.array([2.0, 3.0]))


def test_lon_lat_int_tuple():
    x, y = None, None
    lon, lat = (0, 1), (2, 3)
    is_initialized = False

    for is_gridded in [True, False]:
        x, y, lon, lat, __ = sanitize_input(x, y, lon, lat, is_gridded, is_initialized)

        native_x, native_y, xvec, yvec = func(lon=lon, lat=lat, x=x, y=y)
        assert native_x == "lon"
        assert native_y == "lat"
        assert np.all(xvec == np.array([0.0, 1.0]))
        assert np.all(yvec == np.array([2.0, 3.0]))


def test_lon_lat_single_tuple():
    x, y = None, None
    lon, lat = (0.0), (2.0)
    is_initialized = False

    for is_gridded in [True, False]:
        x, y, lon, lat, __ = sanitize_input(x, y, lon, lat, is_gridded, is_initialized)

        native_x, native_y, xvec, yvec = func(lon=lon, lat=lat, x=x, y=y)
        assert native_x == "lon"
        assert native_y == "lat"
        assert np.all(xvec == np.array([0.0]))
        assert np.all(yvec == np.array([2.0]))


def test_lon_lat_single_value():
    x, y = None, None
    lon, lat = 0.0, 2.0
    is_initialized = False

    for is_gridded in [True, False]:
        x, y, lon, lat, __ = sanitize_input(x, y, lon, lat, is_gridded, is_initialized)

        native_x, native_y, xvec, yvec = func(lon=lon, lat=lat, x=x, y=y)
        assert native_x == "lon"
        assert native_y == "lat"
        assert np.all(xvec == np.array([0.0]))
        assert np.all(yvec == np.array([2.0]))


def test_lon_lat_array():
    x, y = None, None
    lon, lat = np.array([0.0, 1.0, 2.0, 3.0]), np.array([2.0, 3.0, 4.0, 5.0])
    is_initialized = True

    for is_gridded in [True, False]:
        x, y, lon, lat, __ = sanitize_input(x, y, lon, lat, is_gridded, is_initialized)

        native_x, native_y, xvec, yvec = func(lon=lon, lat=lat, x=x, y=y)
        assert native_x == "lon"
        assert native_y == "lat"
        assert np.all(xvec == np.array([0.0, 1.0, 2.0, 3.0]))
        assert np.all(yvec == np.array([2.0, 3.0, 4.0, 5.0]))


def test_lon_lat_int_array():
    x, y = None, None
    lon, lat = np.array([0, 1, 2, 3]), np.array([2, 3, 4, 5])
    is_initialized = True

    for is_gridded in [True, False]:
        x, y, lon, lat, __ = sanitize_input(x, y, lon, lat, is_gridded, is_initialized)

        native_x, native_y, xvec, yvec = func(lon=lon, lat=lat, x=x, y=y)
        assert native_x == "lon"
        assert native_y == "lat"
        assert np.all(xvec == np.array([0, 1, 2, 3]))
        assert np.all(yvec == np.array([2, 3, 4, 5]))
