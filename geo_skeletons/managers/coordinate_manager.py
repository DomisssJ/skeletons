from geo_parameters.metaparameter import MetaParameter
from typing import Union
from geo_parameters.grid import Lon, Lat, X, Y, Inds
import numpy as np
import dask.array as da
from geo_skeletons.errors import VariableExistsError
import geo_parameters as gp

meta_parameters = {"lon": Lon, "lat": Lat, "x": X, "y": Y, "inds": Inds}

SPATIAL_COORDS = ["y", "x", "lat", "lon", "inds"]


class CoordinateManager:
    """Keeps track of coordinates and data variables that are added to classes
    by the decorators."""

    def __init__(self, initial_coords, initial_vars) -> None:
        self._coords = {}
        self._coords["grid"] = []
        self._coords["gridpoint"] = []
        self._coords["initial"] = []

        self._vars = {}
        self._vars["added"] = {}
        self._vars["initial"] = {}

        self._masks = {}
        self._masks["added"] = {}
        self._masks["opposite"] = {}

        self._default_values = {}

        self.magnitudes = {}
        self.directions = {}

        self.meta_coords: dict[str, MetaParameter] = {}
        self.meta_vars: dict[str, MetaParameter] = {}
        self.dir_vars: dict[str, str] = {}
        self.meta_masks: dict[str, MetaParameter] = {}
        self.meta_magnitudes: dict[str, MetaParameter] = {}
        self.meta_directions: dict[str, MetaParameter] = {}

        # E.g. creating a land-mask might be triggered by setting a bathymetry or hs variable
        self.triggers: dict[str, list[tuple[str, tuple[float], tuple[bool]]]] = {}

        self._used_names = []

        self.set_initial_coords(initial_coords)
        self.set_initial_vars(initial_vars)

        # This will be used by decorators to make a deepcopy of the manager for different classes
        self.initial_state = True

    def add_var(
        self,
        name: str,
        coords: str,
        default_value: float,
        dir_type: str = None,
        meta: MetaParameter = None,
    ) -> str:
        """Add a variable that the Skeleton will use."""
        name, meta = gp.decode(name)

        if name in self._used_names:
            raise VariableExistsError(name)

        self._vars["added"][name] = coords
        self._default_values[name] = default_value
        self.meta_vars[name] = meta
        self.dir_vars[name] = dir_type

        self._used_names.append(name)

        return name

    def add_mask(
        self,
        name: str,
        coords: str,
        default_value: int,
        opposite_name: str,
        triggered_by: str,
        valid_range: tuple[float],
        range_inclusive: bool,
    ) -> tuple[str, str]:
        """Add a mask that the Skeleton will use."""
        name, meta = gp.decode(name)
        if f"{name}_mask" in self._used_names:
            raise VariableExistsError(f"{name}_mask")

        self._masks["added"][f"{name}_mask"] = coords

        self._default_values[f"{name}_mask"] = default_value
        self.meta_masks[name] = meta
        self._used_names.append(f"{name}_mask")

        if opposite_name is not None:
            opposite_name, meta = gp.decode(
                opposite_name
            )  # get_name_str_and_meta(opposite_name)
            if f"{opposite_name}_mask" in self._used_names:
                raise VariableExistsError(f"{opposite_name}_mask")

            self._masks["opposite"][f"{opposite_name}_mask"] = f"{name}_mask"
            self._used_names.append(f"{opposite_name}_mask")
        if triggered_by:
            valid_range = tuple([np.inf if r is None else r for r in valid_range])
            if len(valid_range) != 2:
                raise ValueError(f"valid_rang has to be of length 2 (upper, lower)!")
            if isinstance(range_inclusive, bool):
                range_inclusive = (range_inclusive, range_inclusive)

            list_of_computations = self.triggers.get(triggered_by, [])
            list_of_computations.append((name, valid_range, range_inclusive))
            self.triggers[triggered_by] = list_of_computations

        return name, opposite_name

    def add_coord(self, name: str, grid_coord: bool) -> str:
        """Add a coordinate that the Skeleton will use.

        grid_coord = True means that the coordinate describes the outer
        dimensions (e.g. x, y)

        grid_coord = False means that the coordinates describes the inner
        dimensions of one grid point (e.g. frequency, direction)

        E.g. time can be either one (outer dimesnion in spectra, but inner
        dimension in time series)
        """
        name, meta = gp.decode(name)
        if name in self._used_names:
            raise VariableExistsError(name)
        self.meta_coords[name] = meta

        if grid_coord:
            self._coords["grid"].append(name)
        else:
            self._coords["gridpoint"].append(name)

        self._used_names.append(name)
        return name

    def add_magnitude(
        self, name: str, meta: MetaParameter, x: str, y: str, dir: str
    ) -> str:
        if name in self._used_names:
            raise VariableExistsError(name)
        self.magnitudes[name] = {"x": x, "y": y, "dir": dir}
        self.meta_magnitudes[name] = meta
        self._used_names.append(name)

    def add_direction(
        self,
        name: str,
        meta: MetaParameter,
        x: str,
        y: str,
        dir_type: str,
        mag: str,
    ) -> str:
        if name in self._used_names:
            raise VariableExistsError(name)
        self.directions[name] = {"x": x, "y": y, "dir_type": dir_type, "mag": mag}
        self.meta_directions[name] = meta
        self._used_names.append(name)

    def set_initial_vars(self, initial_vars: dict) -> None:
        """Set dictionary containing the initial variables of the Skeleton"""
        if not isinstance(initial_vars, dict):
            raise ValueError("initial_vars needs to be a dict of tuples!")
        for var in self.initial_vars():
            del self.meta_vars[var]
        self._vars["initial"] = initial_vars
        for var in initial_vars:
            self.meta_vars[var] = meta_parameters.get(var)

    def set_initial_coords(self, initial_coords: dict) -> None:
        """Set dictionary containing the initial coordinates of the Skeleton"""
        if not isinstance(initial_coords, list):
            raise ValueError("initial_coords needs to be a list of strings!")
        self._coords["initial"] = initial_coords
        for coord in initial_coords:
            self.meta_coords[coord] = meta_parameters.get(coord)

    def initial_vars(self) -> dict:
        return self._vars["initial"]

    def initial_coords(self) -> dict:
        return self._coords["initial"]

    def added_vars(self) -> dict:
        return self._vars["added"]

    def added_masks(self) -> dict:
        return self._masks["added"]

    def opposite_masks(self) -> dict:
        return self._masks["opposite"]

    def added_coords(self, coords: str = "all") -> list[str]:
        """Returns list of coordinates that have been added to the fixed
        Skeleton coords.

        'all': All added coordinates
        'grid': coordinates for the grid (e.g. z, time)
        'gridpoint': coordinates for a grid point (e.g. frequency, direcion or time)
        """
        if coords not in ["all", "grid", "gridpoint"]:
            print("Variable type needs to be 'all', 'grid' or 'gridpoint'.")
            return None

        if coords == "all":
            return self.added_coords("grid") + self.added_coords("gridpoint")
        return self._coords[coords]

    def coords(self, coords: str = "all") -> list[str]:
        """Returns a list of the coordinates.

        'all' [default]: all coordinates in the Dataset
        'spatial': Dataset coordinates from the Skeleton (x, y, lon, lat, inds)
        'grid': coordinates for the grid (e.g. z, time)
        'gridpoint': coordinates for a grid point (e.g. frequency, direcion or time)
        """

        def list_intersection(list1, list2):
            """Uning intersections of sets doesn't necessarily preserve order"""
            list3 = []
            for val in list1:
                if val in list2:
                    list3.append(val)
            return list3

        if coords not in ["all", "spatial", "grid", "gridpoint"]:
            raise ValueError(
                f"Keyword 'coords' needs to be 'all' (default), 'spatial', 'grid' or 'gridpoint', not {coords}."
            )

        if coords == "spatial":
            return move_time_dim_to_front(
                list_intersection(self.coords("all"), SPATIAL_COORDS)
            )

        if coords == "grid":
            return move_time_dim_to_front(
                self.coords("spatial") + self.added_coords("grid")
            )
        if coords == "gridpoint":
            return move_time_dim_to_front(self.added_coords("gridpoint"))

        if coords == "all":
            return move_time_dim_to_front(
                self.initial_coords() + self.added_coords("all")
            )

    def is_settable(self, name: str) -> bool:
        """Check if the variable etc. is allowed to be set (i.e. is not a magnitude, opposite mask etc.)"""
        return (
            self.added_vars().get(name) is not None
            or self.added_masks().get(name) is not None
        )

    def compute_magnitude(self, x, y):
        if x is None or y is None:
            return None
        return (x**2 + y**2) ** 0.5

    def compute_direction(self, x, y, dir_type: str, dask: bool = True):
        if x is None or y is None:
            return None
        if dask or hasattr(x, "chunks"):
            dirs = da.arctan2(y, x)
        else:
            dirs = np.arctan2(y, x)

        if dir_type == "math":
            return dirs

        if dir_type == "from":
            dirs = 90 - dirs * 180 / np.pi + 180
        elif dir_type == "to":
            dirs = 90 - dirs * 180 / np.pi
        if dask or hasattr(x, "chunks"):
            dirs = da.mod(dirs, 360)
        else:
            dirs = np.mod(dirs, 360)
        return dirs


def move_time_dim_to_front(coord_list) -> list[str]:
    if "time" not in coord_list:
        return coord_list
    coord_list.insert(0, coord_list.pop(coord_list.index("time")))
    return coord_list
