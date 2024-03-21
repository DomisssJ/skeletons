from geo_skeletons import PointSkeleton
from geo_skeletons.decorators import add_coord, add_datavar


def test_point_basic():
    assert PointSkeleton._coord_manager.initial_coords() == ["inds"]
    assert PointSkeleton._coord_manager.initial_vars() == {"y": "inds", "x": "inds"}

    points = PointSkeleton(x=[1, 2], y=[2, 3])
    assert points._coord_manager.initial_coords() == ["inds"]
    assert points._coord_manager.initial_vars() == {"y": "inds", "x": "inds"}

    points2 = PointSkeleton(lon=[1, 2], lat=[2, 3])
    assert points2._coord_manager.initial_coords() == ["inds"]
    assert points2._coord_manager.initial_vars() == {"lat": "inds", "lon": "inds"}

    # Check that deepcopy of coord_manager works and these are not altered
    assert PointSkeleton._coord_manager.initial_coords() == ["inds"]
    assert PointSkeleton._coord_manager.initial_vars() == {"y": "inds", "x": "inds"}

    assert points._coord_manager.initial_coords() == ["inds"]
    assert points._coord_manager.initial_vars() == {"y": "inds", "x": "inds"}


def test_point_added_coord():
    @add_coord(name="w")
    @add_coord(name="z", grid_coord=True)
    class Expanded(PointSkeleton):
        pass

    assert Expanded._coord_manager.initial_coords() == ["inds"]
    assert Expanded._coord_manager.initial_vars() == {"y": "inds", "x": "inds"}
    assert Expanded._coord_manager.added_coords() == ["z", "w"]
    assert Expanded._coord_manager.added_coords("grid") == ["z"]
    assert Expanded._coord_manager.added_coords("gridpoint") == ["w"]

    points = Expanded(x=[1, 2], y=[2, 3], z=[1, 2, 3, 4], w=[6, 7, 8, 9])
    assert points._coord_manager.initial_coords() == ["inds"]
    assert points._coord_manager.initial_vars() == {"y": "inds", "x": "inds"}
    assert points._coord_manager.added_coords() == ["z", "w"]
    assert points._coord_manager.added_coords("grid") == ["z"]
    assert points._coord_manager.added_coords("gridpoint") == ["w"]

    points2 = Expanded(lon=[1, 2], lat=[2, 3], z=[1, 2, 3, 4], w=[6, 7, 8, 9])
    assert points2._coord_manager.initial_coords() == ["inds"]
    assert points2._coord_manager.initial_vars() == {"lat": "inds", "lon": "inds"}
    assert points2._coord_manager.added_coords() == ["z", "w"]
    assert points2._coord_manager.added_coords("grid") == ["z"]
    assert points2._coord_manager.added_coords("gridpoint") == ["w"]

    # Check that deepcopy of coord_manager works and these are not altered
    assert PointSkeleton._coord_manager.initial_coords() == ["inds"]
    assert PointSkeleton._coord_manager.initial_vars() == {"y": "inds", "x": "inds"}
    assert PointSkeleton._coord_manager.added_coords() == []
    assert PointSkeleton._coord_manager.added_coords("grid") == []
    assert PointSkeleton._coord_manager.added_coords("gridpoint") == []

    assert Expanded._coord_manager.initial_coords() == ["inds"]
    assert Expanded._coord_manager.initial_vars() == {"y": "inds", "x": "inds"}
    assert Expanded._coord_manager.added_coords() == ["z", "w"]
    assert Expanded._coord_manager.added_coords("grid") == ["z"]
    assert Expanded._coord_manager.added_coords("gridpoint") == ["w"]

    assert points._coord_manager.initial_coords() == ["inds"]
    assert points._coord_manager.initial_vars() == {"y": "inds", "x": "inds"}
    assert points._coord_manager.added_coords() == ["z", "w"]
    assert points._coord_manager.added_coords("grid") == ["z"]
    assert points._coord_manager.added_coords("gridpoint") == ["w"]


def test_point_added_var():
    @add_datavar(name="eta")
    class Expanded(PointSkeleton):
        pass

    assert Expanded._coord_manager.initial_coords() == ["inds"]
    assert Expanded._coord_manager.initial_vars() == {"y": "inds", "x": "inds"}
    assert Expanded._coord_manager.added_coords() == []
    assert Expanded._coord_manager.added_coords("grid") == []
    assert Expanded._coord_manager.added_coords("gridpoint") == []
    assert Expanded._coord_manager.added_vars() == {"eta": "all"}

    points = Expanded(x=[1, 2], y=[2, 3])
    assert points._coord_manager.initial_coords() == ["inds"]
    assert points._coord_manager.initial_vars() == {"y": "inds", "x": "inds"}
    assert points._coord_manager.added_coords() == []
    assert points._coord_manager.added_coords("grid") == []
    assert points._coord_manager.added_coords("gridpoint") == []
    assert points._coord_manager.added_vars() == {"eta": "all"}

    points2 = Expanded(lon=[1, 2], lat=[2, 3])
    assert points2._coord_manager.initial_coords() == ["inds"]
    assert points2._coord_manager.initial_vars() == {"lat": "inds", "lon": "inds"}
    assert points2._coord_manager.added_coords() == []
    assert points2._coord_manager.added_coords("grid") == []
    assert points2._coord_manager.added_coords("gridpoint") == []
    assert points2._coord_manager.added_vars() == {"eta": "all"}

    # Check that deepcopy of coord_manager works and these are not altered
    assert PointSkeleton._coord_manager.initial_coords() == ["inds"]
    assert PointSkeleton._coord_manager.initial_vars() == {"y": "inds", "x": "inds"}
    assert PointSkeleton._coord_manager.added_coords() == []
    assert PointSkeleton._coord_manager.added_coords("grid") == []
    assert PointSkeleton._coord_manager.added_coords("gridpoint") == []
    assert PointSkeleton._coord_manager.added_vars() == {}

    assert Expanded._coord_manager.initial_coords() == ["inds"]
    assert Expanded._coord_manager.initial_vars() == {"y": "inds", "x": "inds"}
    assert Expanded._coord_manager.added_coords() == []
    assert Expanded._coord_manager.added_coords("grid") == []
    assert Expanded._coord_manager.added_coords("gridpoint") == []
    assert Expanded._coord_manager.added_vars() == {"eta": "all"}

    assert points._coord_manager.initial_coords() == ["inds"]
    assert points._coord_manager.initial_vars() == {"y": "inds", "x": "inds"}
    assert points._coord_manager.added_coords() == []
    assert points._coord_manager.added_coords("grid") == []
    assert points._coord_manager.added_coords("gridpoint") == []
    assert points._coord_manager.added_vars() == {"eta": "all"}


def test_point_added_coord_and_var():
    @add_datavar(name="eta_spatial", coords="spatial")
    @add_datavar(name="eta_gridpoint", coords="gridpoint")
    @add_datavar(name="eta_grid", coords="grid")
    @add_datavar(name="eta_all", coords="all")
    @add_coord(name="w")
    @add_coord(name="z", grid_coord=True)
    class Expanded(PointSkeleton):
        pass

    assert Expanded._coord_manager.initial_coords() == ["inds"]
    assert Expanded._coord_manager.initial_vars() == {"y": "inds", "x": "inds"}
    assert Expanded._coord_manager.added_coords() == ["z", "w"]
    assert Expanded._coord_manager.added_coords("grid") == ["z"]
    assert Expanded._coord_manager.added_coords("gridpoint") == ["w"]
    assert Expanded._coord_manager.added_vars() == {
        "eta_all": "all",
        "eta_grid": "grid",
        "eta_gridpoint": "gridpoint",
        "eta_spatial": "spatial",
    }

    points = Expanded(x=[1, 2], y=[2, 3], z=[1, 2, 3, 4], w=[6, 7, 8, 9, 10])
    assert points._coord_manager.initial_coords() == ["inds"]
    assert points._coord_manager.initial_vars() == {"y": "inds", "x": "inds"}
    assert points._coord_manager.added_coords() == ["z", "w"]
    assert points._coord_manager.added_coords("grid") == ["z"]
    assert points._coord_manager.added_coords("gridpoint") == ["w"]
    assert points._coord_manager.added_vars() == {
        "eta_all": "all",
        "eta_grid": "grid",
        "eta_gridpoint": "gridpoint",
        "eta_spatial": "spatial",
    }
    assert points.eta_all().shape == (2, 4, 5)
    assert points.eta_grid().shape == (2, 4)
    assert points.eta_gridpoint().shape == (5,)
    assert points.eta_spatial().shape == (2,)

    points2 = Expanded(lon=[1, 2], lat=[2, 3], z=[1, 2, 3, 4], w=[6, 7, 8, 9, 10])
    assert points2._coord_manager.initial_coords() == ["inds"]
    assert points2._coord_manager.initial_vars() == {"lat": "inds", "lon": "inds"}
    assert points2._coord_manager.added_coords() == ["z", "w"]
    assert points2._coord_manager.added_coords("grid") == ["z"]
    assert points2._coord_manager.added_coords("gridpoint") == ["w"]
    assert points2._coord_manager.added_vars() == {
        "eta_all": "all",
        "eta_grid": "grid",
        "eta_gridpoint": "gridpoint",
        "eta_spatial": "spatial",
    }

    assert points2.eta_all().shape == (2, 4, 5)
    assert points2.eta_grid().shape == (2, 4)
    assert points2.eta_gridpoint().shape == (5,)
    assert points2.eta_spatial().shape == (2,)

    # Check that deepcopy of coord_manager works and these are not altered
    assert PointSkeleton._coord_manager.initial_coords() == ["inds"]
    assert PointSkeleton._coord_manager.initial_vars() == {"y": "inds", "x": "inds"}
    assert PointSkeleton._coord_manager.added_coords() == []
    assert PointSkeleton._coord_manager.added_coords("grid") == []
    assert PointSkeleton._coord_manager.added_coords("gridpoint") == []
    assert PointSkeleton._coord_manager.added_vars() == {}

    assert Expanded._coord_manager.initial_coords() == ["inds"]
    assert Expanded._coord_manager.initial_vars() == {"y": "inds", "x": "inds"}
    assert Expanded._coord_manager.added_coords() == ["z", "w"]
    assert Expanded._coord_manager.added_coords("grid") == ["z"]
    assert Expanded._coord_manager.added_coords("gridpoint") == ["w"]
    assert Expanded._coord_manager.added_vars() == {
        "eta_all": "all",
        "eta_grid": "grid",
        "eta_gridpoint": "gridpoint",
        "eta_spatial": "spatial",
    }
    assert points._coord_manager.initial_coords() == ["inds"]
    assert points._coord_manager.initial_vars() == {"y": "inds", "x": "inds"}
    assert points._coord_manager.added_coords() == ["z", "w"]
    assert points._coord_manager.added_coords("grid") == ["z"]
    assert points._coord_manager.added_coords("gridpoint") == ["w"]
    assert points._coord_manager.added_vars() == {
        "eta_all": "all",
        "eta_grid": "grid",
        "eta_gridpoint": "gridpoint",
        "eta_spatial": "spatial",
    }