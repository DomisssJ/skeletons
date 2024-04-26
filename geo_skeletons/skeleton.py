import numpy as np
import xarray as xr
import utm as utm_module
from copy import copy
from .managers.dataset_manager import DatasetManager
from .managers.dask_manager import DaskManager
from .managers.reshape_manager import ReshapeManager
from .managers.metadata_manager import MetaDataManager
from .managers.dir_type_manager import DirTypeManager

from .managers.utm_manager import UTMManager
from typing import Iterable, Union
from .aux_funcs import distance_funcs, array_funcs, utm_funcs
from .errors import DataWrongDimensionError

from typing import Iterable
import dask.array as da
from copy import deepcopy
from .decorators import add_datavar, add_magnitude
from .iter import SkeletonIterator


class Skeleton:
    """Contains methods and data of the spatial x,y / lon, lat coordinates and
    makes possible conversions between them.

    Keeps track of the native structure of the grid (cartesian UTM / sperical).
    """

    chunks = None

    def __init__(
        self,
        x=None,
        y=None,
        lon=None,
        lat=None,
        name: str = "LonelySkeleton",
        utm: tuple[int, str] = None,
        chunks: Union[tuple[int], str] = None,
        **kwargs,
    ) -> None:
        self.name = name
        if chunks is not None:
            self.chunks = chunks
        self._init_structure(x, y, lon, lat, utm=utm, **kwargs)

    def add_datavar(
        self, name: str, coord_group: str = "all", default_value: float = 0.0
    ) -> None:
        self = add_datavar(
            name=name, coord_group=coord_group, default_value=default_value, append=True
        )(self)
        self._ds_manager.coord_manager = self.core
        self.meta._ds_manager = self._ds_manager

    def add_magnitude(
        self, name: str, x: str, y: str, direction: str = None, dir_type: str = None
    ) -> None:
        self = add_magnitude(
            name=name, x=x, y=y, direction=direction, dir_type=dir_type, append=True
        )(self)
        self._ds_manager.coord_manager = self.core
        self.meta._ds_manager = self._ds_manager

    @classmethod
    def from_ds(
        cls,
        ds: xr.Dataset,
        chunks: Union[tuple[int], str] = "auto",
        **kwargs,
    ):
        """Generats a PointSkeleton from an xarray Dataset. All coordinates must be present, but only matching data variables included.

        Missing coordinates can be provided as kwargs."""

        # Getting mandatory spatial variables
        lon, lat = ds.get("lon"), ds.get("lat")
        x, y = ds.get("x"), ds.get("y")

        if lon is not None:
            lon = lon.values
        if lat is not None:
            lat = lat.values
        if x is not None:
            x = x.values
        if y is not None:
            y = y.values

        if x is None and y is None and lon is None and lat is None:
            raise ValueError("Can't find x/y lon/lat pair in Dataset!")

        # Gather other coordinates
        coords = cls.core.coords("all")  # list(ds.coords) + list(kwargs.keys())
        additional_coords = {}
        for coord in [
            coord for coord in coords if coord not in ["inds", "lon", "lat", "x", "y"]
        ]:
            ds_val = ds.get(coord)

            provided_val = kwargs.get(coord)
            val = provided_val if provided_val is not None else ds_val

            if val is None:
                raise KeyError(
                    f"Can't find required coordinate {coord} in Dataset or in kwargs!"
                )
            else:
                if isinstance(val, xr.DataArray):
                    val = val.data
            additional_coords[coord] = val

        # Initialize Skeleton
        points = cls(x=x, y=y, lon=lon, lat=lat, chunks=chunks, **additional_coords)

        # Set data variables and masks that exist
        for data_var in points.core.non_coord_objects():
            val = ds.get(data_var)
            if val is not None:
                points.set(data_var, val)
                points.meta.set(ds.get(data_var).attrs, name=data_var)
        points.meta.set(ds.attrs)

        return points

    def _init_structure(
        self, x=None, y=None, lon=None, lat=None, utm=None, **kwargs
    ) -> None:
        """Determines grid type (Cartesian/Spherical), generates a DatasetManager
        and initializes the Xarray dataset within the DatasetManager.

        The initial coordinates and variables are read from the method of the
        subclass (e.g. PointSkeleton)
        """

        # Don't want to alter the CoordManager of the class
        if not self.core._is_initialized():
            self.core = deepcopy(self.core)  # Makes a copy of the class coord_manager
            self.meta = deepcopy(self.meta)
            self.meta._coord_manager = self.core

        # # The manager will contain the Xarray Dataset
        if self.ds() is None:
            self._ds_manager = DatasetManager(self.core)
        else:
            self._ds_manager.coord_manager = self.core
        self.meta._ds_manager = self._ds_manager

        x, y, lon, lat, kwargs = array_funcs.sanitize_input(
            x, y, lon, lat, self.is_gridded(), **kwargs
        )

        x_str, y_str, xvec, yvec = utm_funcs.will_grid_be_spherical_or_cartesian(
            x, y, lon, lat
        )
        self.core.x_str = x_str
        self.core.y_str = y_str

        # Reset initial coordinates and data variables (default are 'x','y' but might now be 'lon', 'lat')
        self.core.set_initial_coords(self._initial_coords(spherical=(x_str == "lon")))
        self.core.set_initial_vars(self._initial_vars(spherical=(x_str == "lon")))

        self._ds_manager.create_structure(
            xvec, yvec, self.core.x_str, self.core.y_str, **kwargs
        )

        self._dir_type_manager = DirTypeManager(coord_manager=self.core)

        self.utm = UTMManager(
            lat=self.edges("lat", strict=True),
            lon=self.edges("lon", strict=True),
            metadata_manager=self.meta,
        )
        self.utm.set(utm, silent=True)

        # Set metadata
        for name in self.core.all_objects("all"):
            metavar = self.core.get(name).meta
            if metavar is not None:
                self.meta.append(metavar.meta_dict(), name)

    def absorb(self, skeleton_to_absorb, dim: str) -> None:
        """Absorb another object of same type over a centrain dimension.
        For a PointSkeleton the inds-variable reorganized if dim='inds' is given."""
        if not self.is_gridded() and dim == "inds":
            inds = skeleton_to_absorb.inds() + len(self.inds())
            skeleton_to_absorb.ds()["inds"] = inds

        new_skeleton = self.from_ds(
            xr.concat(
                [self.ds(), skeleton_to_absorb.ds()], dim=dim, data_vars="minimal"
            ).sortby(dim)
        )
        return new_skeleton

    def sel(self, **kwargs):
        return self.from_ds(self.ds().sel(**kwargs))

    def isel(self, **kwargs):
        return self.from_ds(self.ds().isel(**kwargs))

    def insert(self, name: str, data: np.ndarray, **kwargs) -> None:
        """Inserts a slice of data into the Skeleton.

        If data named 'geodata' has shape dimension ('time', 'inds', 'threshold') and shape (57, 10, 3), then
        data_slice having the threshold=0.4 and time='2023-11-08 12:00:00' having shape=(10,) can be inserted by using the values:

        .insert(name='geodata', data=data_slice, time='2023-11-08 12:00:00', threshold=0.4)
        """
        dims = self.ds().dims
        index_kwargs = {}
        for dim in dims:
            val = kwargs.get(dim)
            if val is not None:
                index_kwargs[dim] = np.where(self.get(dim) == val)[0][0]

        self.ind_insert(name=name, data=data, **index_kwargs)

    def ind_insert(self, name: str, data: np.ndarray, **kwargs) -> None:
        """Inserts a slice of data into the Skeleton.

        If data named 'geodata' has dimension ('time', 'inds', 'threshold') and shape (57, 10, 3), then
        data_slice having the first threshold and first time can be inserted by using the index values:

        .ind_insert(name='geodata', data=data_slice, time=0, threshold=0)"""

        dims = self.ds().dims
        index_list = list(np.arange(len(dims)))

        for n, dim in enumerate(dims):
            var = self.get(dim)
            if var is None:
                raise KeyError(f"No coordinate {dim} exists!")
            ind = kwargs.get(dim, slice(len(var)))
            index_list[n] = ind

        old_data = self.get(name, squeeze=False).copy()
        N = len(old_data.shape)
        data_str = "old_data["
        for n in range(N):
            data_str += f"{index_list[n]},"
        data_str = data_str[:-1]
        data_str += "] = data"
        exec(data_str)
        self.set(name, old_data, allow_reshape=False)
        return

    def set(
        self,
        name: str,
        data=None,
        dir_type: str = None,
        allow_reshape: bool = True,
        allow_transpose: bool = False,
        coords: list[str] = None,
        silent: bool = True,
        chunks: Union[tuple, str] = None,
    ) -> None:
        """Sets the data using the following logic:

        data [None]: numpy/dask array. If None [Default], an empty array is set.

        Any numpy array is converted to a dask-array if dask-mode is set with .activate_dask().
        If keyword 'chunks' is set, then conversion to dask is always done.

        If given data is a dask array, then it is never rechunked, but used as is.

        allow_reshape [True]: Allow squeezing out trivial dimensions.
        allow_transpose [False]: Allow trying to transpose exactly two non-trivial dimensions

        Otherwise, data is assumed to be in the right dimension, but can also be reshaped:

        1) If 'coords' (e.g. ['freq',' inds']) is given, then data is reshaped assuming data is in that order.
        2) If data is a DataArray, then 'coords' is set using the information in the DataArray.
        3) If data has any trivial dimensions, then those are squeezed.
        4) If data is missing any trivial dimension, then those are expanded.
        5) If data along non-trivial dimensions is two-dimensional, then a transpose is attemted.

        NB! For 1), only non-trivial dimensions need to be identified

        silent [True]: Don't output what reshaping is being performed.

        """

        if not isinstance(name, str):
            raise TypeError(
                f"'name' must be of type 'str', not '{type(name).__name__}'!"
            )

        # Takes care of dask/numpy operations so we don't have to check every tim
        dask_manager = DaskManager(chunks=chunks or self.chunks)

        if data is None:
            data = self.get(name, empty=True, squeeze=False, dir_type=dir_type)

        # Make constant array if given data has no shape
        # Return original data if it has shape
        data = dask_manager.constant_array(
            data, self.shape(name), dask=(self.dask() or chunks is not None)
        )

        # If a DataArray is given, then read the dimensions from there if not explicitly provided in a keyword
        if isinstance(data, xr.DataArray):
            coords = coords or list(data.dims)
            data = data.data

        if self.dask() or chunks is not None:
            data = dask_manager.dask_me(data, chunks=chunks)

        data = self._reshape_data(
            name,
            data,
            coords,
            dask_manager,
            silent,
            allow_reshape,
            allow_transpose,
        )

        # Masks are stored as integers
        if name in self.core.masks("all"):
            data = data.astype(int)

        if name in self.core.magnitudes("all"):
            self._set_magnitude(
                name=name,
                data=data,
                dask_manager=dask_manager,
            )
        elif name in self.core.directions("all"):
            self._set_direction(
                name=name,
                data=data,
                dir_type=dir_type,
                dask_manager=dask_manager,
            )
        else:
            self._set_data(
                name=name,
                data=data,
            )

        return

    def _reshape_data(
        self,
        name: str,
        data,
        coords: list[str],
        dask_manager: DaskManager,
        silent: bool,
        allow_reshape: bool,
        allow_transpose: bool,
    ):
        """Reshapes the data using the following logic:

        allow_reshape [True]: Allow squeezing out trivial dimensions.
        allow_transpose [False]: Allow trying to transpose exactly two non-trivial dimensions

        Otherwise, data is assumed to be in the right dimension, but can also be reshaped:

        1) If 'coords' (e.g. ['freq',' inds']) is given, then data is reshaped assuming data is in that order.
        2) If data is a DataArray, then 'coords' is set using the information in the DataArray.
        3) If data has any trivial dimensions, then those are squeezed.
        4) If data is missing any trivial dimension, then those are expanded.
        5) If data along non-trivial dimensions is two-dimensional, then a transpose is attemted.

        NB! For 1), only non-trivial dimensions need to be identified

        silent [True]: Don't output what reshaping is being performed.

        If data cannot be reshaped, a DataWrongDimensionError is raised.
        """
        reshape_manager = ReshapeManager(dask_manager=dask_manager, silent=silent)
        coord_type = self.core.coord_group(name)

        # Do explicit reshape if coordinates of the provided data is given
        if coords is not None:
            # Some dimensions of the provided data might not exist in the Skeleton
            # If they are trivial then they don't matter, so squeeze them out
            squeezed_coords = [
                c for c in coords if self.get(c) is not None and len(self.get(c)) > 1
            ]
            data = reshape_manager.explicit_reshape(
                data.squeeze(),
                data_coords=squeezed_coords,
                expected_coords=self.core.coords(coord_type),
            )

            # Unsqueeze the data before setting to get back trivial dimensions
            data = reshape_manager.unsqueeze(data, expected_shape=self.size(coord_type))

        # Try to set the data
        if data.shape != self.shape(name):
            # if not (allow_reshape or allow_transpose):
            #     raise data_error

            # If we are here then the data could not be set, but we are allowed to try to reshape
            if not silent:
                print(f"Size of {name} does not match size of {type(self).__name__}...")

            # Save this for messages
            original_data_shape = data.shape

            if allow_transpose:
                data = reshape_manager.transpose_2d(
                    data, expected_squeezed_shape=self.size(coord_type, squeeze=True)
                )
            if allow_reshape:
                data = reshape_manager.unsqueeze(
                    data, expected_shape=self.size(coord_type)
                )
            if data is None:
                raise DataWrongDimensionError(
                    original_data_shape, self.shape(name)
                )  # Reshapes have failed

            if not silent:
                print(f"Reshaping data {original_data_shape} -> {data.shape}...")
        return data

    def _set_magnitude(
        self,
        name: str,
        data,
        dask_manager: DaskManager,
    ) -> None:
        """Sets a magnitude variable.

        Calculates x- and y- components and sets them based on set connected direction.

        Data needs to be exactly right shape."""
        obj = self.core.get(name)
        x_component, y_component = obj.x, obj.y
        dir_data = self.get(obj.direction.name, dir_type="math")

        s = dask_manager.sin(dir_data)
        c = dask_manager.cos(dir_data)
        ux = data * c
        uy = data * s

        self._set_data(
            name=x_component,
            data=ux,
        )
        self._set_data(
            name=y_component,
            data=uy,
        )

    def _set_direction(
        self,
        name: str,
        data,
        dir_type: str,
        dask_manager: DaskManager,
    ) -> None:
        """Sets a directeion variable.

        Calculates x- and y- components and sets them based on set connected magnitude.

        Data needs to be exactly right shape."""
        obj = self.core.get(name)
        x_component, y_component = obj.x, obj.y
        mag_data = self.get(obj.magnitude.name)

        dir_type = dir_type or obj.dir_type

        data = self._dir_type_manager.convert_to_math_dir(data, dir_type)

        s = dask_manager.sin(data)
        c = dask_manager.cos(data)
        ux = mag_data * c
        uy = mag_data * s

        self._set_data(
            name=x_component,
            data=ux,
        )
        self._set_data(
            name=y_component,
            data=uy,
        )

    def _set_data(
        self,
        name: str,
        data,
    ) -> None:
        """Sets a data variable to the underlying dataset.

        Triggers setting metadata of the variable and possible connected masks."""
        coord_group = self.core.coord_group(name)
        coords = self.core.coords(coord_group)
        self._ds_manager.set(data=data, data_name=name, coords=coords)
        self._trigger_masks(name, data)

    def _trigger_masks(self, name: str, data) -> None:
        """Set any masks that are triggered by setting a specific data variable
        E.g. Set new 'land_mask' when 'topo' is set."""
        for mask in self.core.triggers(name):

            if mask.range_inclusive[0]:
                low_mask = data >= mask.valid_range[0]
            else:
                low_mask = data > mask.valid_range[0]

            if mask.range_inclusive[1]:
                high_mask = data <= mask.valid_range[1]
            else:
                high_mask = data < mask.valid_range[1]

            mask_array = np.logical_and(low_mask, high_mask)
            self.set(mask.name, mask_array)

    def get(
        self,
        name,
        strict: bool = False,
        empty: bool = False,
        data_array: bool = False,
        dir_type: str = None,
        squeeze: bool = True,
        dask: bool = None,
        **kwargs,
    ):
        """Gets a mask or data variable as an array.

        strict [False]: Return 'None' if data not set. Otherwise returns empty array.
        empty [False]: Return an array full with default values even if variable is set.
        data_array [False]: Return data as an xarray DataArray.
        squeeze [True]: Smart squeeze out trivial dimensions, but return at least 1d array.
        boolean_mask [False]: Convert array to a boolean array.
        dask [None]: Return dask array [True] or numpy array [False]. Default: Use set dask-mode
        """
        if self.ds() is None:
            return None

        if dir_type not in ["to", "from", "math", None]:
            raise ValueError(
                f"'dir_type' needs to be 'to', 'from' or 'math' (or None), not {dir_type}"
            )

        if name in self.core.magnitudes():
            data = self._get_magnitude(
                name=name,
                strict=strict,
                empty=empty,
                **kwargs,
            )
        elif name in self.core.directions():
            data = self._get_direction(
                name=name,
                strict=strict,
                dir_type=dir_type,
                empty=empty,
                **kwargs,
            )
        else:
            data = self._ds_manager.get(name, empty=empty, strict=strict, **kwargs)
            if data is None:
                return None

            if dir_type is not None:
                set_dir_type = self._dir_type_manager.get_dir_type(name)
                data = self._dir_type_manager.convert(
                    data, in_type=set_dir_type, out_type=dir_type
                )

        if not isinstance(data, xr.DataArray):
            return None

        # The coordinates are never given as dask arrays
        if name in self.core.coords("all"):
            dask = False

        if name in self.core.masks("all"):
            data = data.astype(bool)

        if squeeze:
            data = self._smart_squeeze(name, data)

        # Use dask mode default if not explicitly overridden
        if dask is None:
            dask = self.dask()
        # Need to make sure we set chunks if dask mode is not activated
        # Can't use chunks if dask is not requested
        chunks = self.chunks or "auto" if dask else None
        dask_manager = DaskManager(chunks)
        data = dask_manager.dask_me(data) if dask else dask_manager.undask_me(data)

        if not data_array:
            data = data.data

        return data

    def _get_direction(
        self,
        name,
        strict: bool = False,
        empty: bool = False,
        dir_type: str = None,
        **kwargs,
    ):

        x_data = self._ds_manager.get(
            self.core.get(name).x,
            empty=empty,
            strict=strict,
            **kwargs,
        )
        y_data = self._ds_manager.get(
            self.core.get(name).y,
            empty=empty,
            strict=strict,
            **kwargs,
        )

        if x_data is None or y_data is None:
            return None

        dir_type = dir_type or self.core.get(name).dir_type
        data = self._dir_type_manager.compute_math_direction(x_data, y_data)
        data = self._dir_type_manager.convert_from_math_dir(data, dir_type=dir_type)

        return data

    def _get_magnitude(
        self,
        name,
        strict: bool = False,
        empty: bool = False,
        **kwargs,
    ):
        x_data = self._ds_manager.get(
            self.core.get(name).x,
            empty=empty,
            strict=strict,
            **kwargs,
        )
        y_data = self._ds_manager.get(
            self.core.get(name).y,
            empty=empty,
            strict=strict,
            **kwargs,
        )
        data = self._dir_type_manager.compute_magnitude(x_data, y_data)
        return data

    def _smart_squeeze(self, name: str, data):
        """Squeezes the data but takes care that one dimension is kept.

        Spatial dims are not protected, but if the results is a 0-dim,
        then 'inds' or 'lat' is kept."""
        dims_to_drop = [
            dim
            for dim in self.core.coords("all")
            if self.shape(dim)[0] == 1 and dim in data.coords
        ]

        # If it looks like we are dropping all coords, then save the spatial ones
        if dims_to_drop == list(data.coords):
            dims_to_drop = list(
                set(dims_to_drop) - set(self.core.coords("spatial")) - set([name])
            )

        if dims_to_drop:
            data = data.squeeze(dim=dims_to_drop, drop=True)

        return data

    def coord_squeeze(self, coords: list[str]) -> list[str]:
        return [c for c in coords if len(self.get(c)) > 1] or self.core.coords(
            "spatial"
        )

    def ds(self):
        if not hasattr(self, "_ds_manager"):
            return None
        return self._ds_manager.ds()

    def find_cf(self, standard_name: str) -> list[str]:
        """Finds the variable names that have the given standard name"""
        names = []

        for name in self.core.all_objects():
            obj = self.core.get(name)
            if obj.meta is None:
                continue
            if (
                obj.meta.standard_name() == standard_name
                or obj.meta.standard_name(alias=True) == standard_name
            ):
                names.append(obj.name)

        return names

    def size(
        self, coord_group: str = "all", squeeze: bool = False, **kwargs
    ) -> tuple[int]:
        """Returns the size of the Dataset.

        'all' [default]: size of entire Dataset
        'spatial': size over coordinates from the Skeleton (x, y, lon, lat, inds)
        'grid': size over coordinates for the grid (e.g. z, time) ans the spatial coordinates
        'gridpoint': size over coordinates for a grid point (e.g. frequency, direcion or time)
        """

        if self.ds() is None:
            return None

        if coord_group not in ["all", "spatial", "grid", "gridpoint"]:
            raise KeyError(
                f"coords should be 'all', 'spatial', 'grid' or 'gridpoint', not {coord_group}!"
            )
        size = self._ds_manager.coords_to_size(self.core.coords(coord_group), **kwargs)

        if squeeze:
            size = tuple([s for s in size if s > 1])
        return size

    def shape(self, var, squeeze: bool = False, **kwargs) -> tuple[int]:
        """Returns the size of one specific data variable"""
        if var in self.core.coords("all"):
            return self.get(var, squeeze=False).shape
        coord_group = self.core.coord_group(var)
        return self.size(coord_group=coord_group, squeeze=squeeze, **kwargs)

    def inds(self, **kwargs) -> np.ndarray:
        if self.ds() is None:
            return None
        return self.get("inds", **kwargs)

    def x(
        self,
        native: bool = False,
        strict: bool = False,
        normalize: bool = False,
        utm: tuple[int, str] = None,
        **kwargs,
    ) -> np.ndarray:
        """Returns the cartesian x-coordinate.

        If the grid is spherical, a conversion to UTM coordinates is made based on the medain latitude.

        If native=True, then longitudes are returned for spherical grids instead
        If strict=True, then None is returned if grid is sperical

        native=True overrides strict=True for spherical grids

        Give utm to get cartesian coordinates in specific utm system. Otherwise defaults to the one set for the grid.
        """

        if self.ds() is None:
            return None

        if not self.core.is_cartesian() and native:
            return self.lon(**kwargs)

        if not self.core.is_cartesian() and strict:
            return None

        if self.core.is_cartesian() and (self.utm.zone() == utm or utm is None):
            x = self._ds_manager.get("x", **kwargs).values.copy()
            if normalize:
                x = x - min(x)
            return x

        if utm is None:
            number, letter = self.utm.zone()
        else:
            number, letter = utm

        if (
            self.is_gridded()
        ):  # This will rotate the grid, but is best estimate to keep it strucutred
            lat = np.median(self.lat(**kwargs))
            print(
                "Regridding spherical grid to cartesian coordinates will cause a rotation! Use 'x, _ = skeleton.xy()' to get a list of all points."
            )
            x, __, __, __ = utm_module.from_latlon(
                lat,
                self.lon(**kwargs),
                force_zone_number=number,
                force_zone_letter=letter,
            )
        else:
            lat = self.lat(**kwargs)
            lat = utm_funcs.cap_lat_for_utm(lat)

            posmask = lat >= 0
            negmask = lat < 0
            x = np.zeros(len(lat))
            if np.any(posmask):
                x[posmask], __, __, __ = utm_module.from_latlon(
                    lat[posmask],
                    self.lon(**kwargs)[posmask],
                    force_zone_number=number,
                    force_zone_letter=letter,
                )
            if np.any(negmask):
                x[negmask], __, __, __ = utm_module.from_latlon(
                    -lat[negmask],
                    self.lon(**kwargs)[negmask],
                    force_zone_number=number,
                    force_zone_letter=letter,
                )

        if normalize:
            x = x - min(x)

        return x

    def y(
        self,
        native: bool = False,
        strict: bool = False,
        normalize: bool = False,
        utm: tuple[int, str] = None,
        **kwargs,
    ) -> np.ndarray:
        """Returns the cartesian y-coordinate.

        If the grid is spherical, a conversion to UTM coordinates is made based on the medain latitude.

        If native=True, then latitudes are returned for spherical grids instead
        If strict=True, then None is returned if grid is sperical

        native=True overrides strict=True for spherical grids

        Give utm to get cartesian coordinates in specific utm system. Otherwise defaults to the one set for the grid.
        """

        if self.ds() is None:
            return None

        if not self.core.is_cartesian() and native:
            return self.lat(**kwargs)

        if not self.core.is_cartesian() and strict:
            return None

        if self.core.is_cartesian() and (self.utm.zone() == utm or utm is None):
            y = self._ds_manager.get("y", **kwargs).values.copy()
            if normalize:
                y = y - min(y)
            return y

        if utm is None:
            number, letter = self.utm.zone()
        else:
            number, letter = utm
        posmask = self.lat(**kwargs) >= 0
        negmask = self.lat(**kwargs) < 0
        if (
            self.is_gridded()
        ):  # This will rotate the grid, but is best estimate to keep it strucutred
            lon = np.median(self.lon(**kwargs))
            print(
                "Regridding spherical grid to cartesian coordinates will cause a rotation! Use '_, y = skeleton.xy()' to get a list of all points."
            )
            y = np.zeros(len(self.lat(**kwargs)))
            if np.any(posmask):
                _, y[posmask], __, __ = utm_module.from_latlon(
                    self.lat(**kwargs)[posmask],
                    lon,
                    force_zone_number=number,
                    force_zone_letter=letter,
                )
            if np.any(negmask):
                _, y[negmask], __, __ = utm_module.from_latlon(
                    -self.lat(**kwargs)[negmask],
                    lon,
                    force_zone_number=number,
                    force_zone_letter=letter,
                )
                y[negmask] = -y[negmask]
        else:
            lat = utm_funcs.cap_lat_for_utm(self.lat(**kwargs))
            y = np.zeros(len(self.lat(**kwargs)))
            if np.any(posmask):
                _, y[posmask], __, __ = utm_module.from_latlon(
                    lat[posmask],
                    self.lon(**kwargs)[posmask],
                    force_zone_number=number,
                    force_zone_letter=letter,
                )
            if np.any(negmask):
                _, y[negmask], __, __ = utm_module.from_latlon(
                    -lat[negmask],
                    self.lon(**kwargs)[negmask],
                    force_zone_number=number,
                    force_zone_letter=letter,
                )
                y[negmask] = -y[negmask]

        if normalize:
            y = y - min(y)

        return y

    def lon(self, native: bool = False, strict=False, **kwargs) -> np.ndarray:
        """Returns the spherical lon-coordinate.

        If the grid is cartesian, a conversion from UTM coordinates is made based on the medain y-coordinate.

        If native=True, then x-coordinatites are returned for cartesian grids instead
        If strict=True, then None is returned if grid is cartesian

        native=True overrides strict=True for cartesian grids
        """
        if self.ds() is None:
            return None

        if self.core.is_cartesian() and native:
            return self.x(**kwargs)

        if self.core.is_cartesian() and strict:
            return None

        if self.core.is_cartesian():
            if (
                self.is_gridded()
            ):  # This will rotate the grid, but is best estimate to keep it strucutred
                y = np.median(self.y(**kwargs))
                print(
                    "Regridding cartesian grid to spherical coordinates will cause a rotation! Use 'lon, _ = skeleton.lonlat()' to get a list of all points."
                )
            else:
                y = self.y(**kwargs)
            number, letter = self.utm.zone()
            if number is None:
                print(
                    "Need to set an UTM-zone, e.g. set_utm((33,'W')), to get longitudes!"
                )
                return None
            __, lon = utm_module.to_latlon(
                self.x(**kwargs),
                np.mod(y, 10_000_000),
                zone_number=number,
                zone_letter=letter,
                strict=False,
            )

            return lon
        return self._ds_manager.get("lon", **kwargs).values.copy()

    def lat(self, native: bool = False, strict=False, **kwargs) -> np.ndarray:
        """Returns the spherical lat-coordinate.

        If the grid is cartesian, a conversion from UTM coordinates is made based on the medain y-coordinate.

        If native=True, then y-coordinatites are returned for cartesian grids instead
        If strict=True, then None is returned if grid is cartesian

        native=True overrides strict=True for cartesian grids
        """
        if self.ds() is None:
            return None

        if self.core.is_cartesian() and native:
            return self.y(**kwargs)

        if self.core.is_cartesian() and strict:
            return None

        if self.core.is_cartesian():
            if (
                self.is_gridded()
            ):  # This will rotate the grid, but is best estimate to keep it strucutred
                x = np.median(self.x(**kwargs))
                print(
                    "Regridding cartesian grid to spherical coordinates will cause a rotation! Use '_, lat = skeleton.lonlat()' to get a list of all points."
                )
            else:
                x = self.x(**kwargs)

            number, letter = self.utm.zone()
            if number is None:
                print(
                    "Need to set an UTM-zone, e.g. set_utm((33,'W')), to get latitudes!"
                )
                return None
            lat, __ = utm_module.to_latlon(
                x,
                np.mod(self.y(**kwargs), 10_000_000),
                zone_number=number,
                zone_letter=letter,
                strict=False,
            )
            return lat

        return self._ds_manager.get("lat", **kwargs).values.copy()

    def edges(
        self, coord: str, native: bool = False, strict=False
    ) -> tuple[float, float]:
        """Min and max values of x. Conversion made for sperical grids."""
        if self.ds() is None:
            return (None, None)

        if coord not in ["x", "y", "lon", "lat"]:
            print("coord need to be 'x', 'y', 'lon' or 'lat'.")
            return

        if coord in ["x", "y"]:
            x, y = self.xy(native=native, strict=strict)
        else:
            x, y = self.lonlat(native=native, strict=strict)

        if coord in ["x", "lon"]:
            val = x
        else:
            val = y

        if val is None:
            return (None, None)

        return np.min(val), np.max(val)

    def nx(self) -> int:
        """Length of x/lon-vector."""
        if self.ds() is None:
            return 0
        return len(self.x(native=True))

    def ny(self):
        """Length of y/lat-vector."""
        if self.ds() is None:
            return 0
        return len(self.y(native=True))

    def dx(self, native: bool = False, strict: bool = False):
        """Mean grid spacing of the x vector. Conversion made for
        spherical grids."""
        if self.ds() is None:
            return None

        if not self.core.is_cartesian() and strict and (not native):
            return None

        if self.nx() == 1:
            return 0.0

        return (max(self.x(native=native)) - min(self.x(native=native))) / (
            self.nx() - 1
        )

    def dy(self, native: bool = False, strict: bool = False):
        """Mean grid spacing of the y vector. Conversion made for
        spherical grids."""
        if self.ds() is None:
            return None

        if not self.core.is_cartesian() and strict and (not native):
            return None

        if self.ny() == 1:
            return 0.0

        return (max(self.y(native=native)) - min(self.y(native=native))) / (
            self.ny() - 1
        )

    def dlon(self, native: bool = False, strict: bool = False):
        """Mean grid spacing of the longitude vector. Conversion made for
        cartesian grids."""
        if self.ds() is None:
            return None

        if self.core.is_cartesian() and strict and (not native):
            return None
        if self.nx() == 1:
            return 0.0

        return (max(self.lon(native=native)) - min(self.lon(native=native))) / (
            self.nx() - 1
        )

    def dlat(self, native: bool = False, strict: bool = False):
        """Mean grid spacing of the latitude vector. Conversion made for
        cartesian grids."""
        if self.ds() is None:
            return None

        if self.core.is_cartesian() and strict and (not native):
            return None
        if self.ny() == 1:
            return 0.0

        return (max(self.lat(native=native)) - min(self.lat(native=native))) / (
            self.ny() - 1
        )

    def yank_point(
        self,
        lon: Union[float, Iterable[float]] = None,
        lat: Union[float, Iterable[float]] = None,
        x: Union[float, Iterable[float]] = None,
        y: Union[float, Iterable[float]] = None,
        unique: bool = False,
        fast: bool = False,
    ) -> dict:
        """Finds points nearest to the x-y, lon-lat points provided and returns dict of corresponding indeces.

        All Skeletons: key 'dx' (distance to nearest point in km)

        PointSkelton: keys 'inds'
        GriddedSkeleton: keys 'inds_x' and 'inds_y'

        Set unique=True to remove any repeated points.
        Set fast=True to use UTM casrtesian search for low latitudes."""

        if self.core.is_cartesian():
            fast = True

        # If lon/lat is given, convert to cartesian and set grid UTM zone to match the query point
        x = array_funcs.force_to_iterable(x)
        y = array_funcs.force_to_iterable(y)
        lon = array_funcs.force_to_iterable(lon)
        lat = array_funcs.force_to_iterable(lat)

        if all([x is None for x in (x, y, lon, lat)]):
            raise ValueError("Give either x-y pair or lon-lat pair!")

        orig_zone = self.utm.zone()
        if lon is not None and lat is not None:
            if self.core.is_cartesian():
                x, y, __, __ = utm_module.from_latlon(
                    lat,
                    lon,
                    force_zone_number=orig_zone[0],
                    force_zone_letter=orig_zone[1],
                )
            else:
                x, y, zone_number, zone_letter = utm_module.from_latlon(lat, lon)
                self.utm.set((zone_number, zone_letter), silent=True)
        else:
            if orig_zone[0] is not None:
                lat, lon = utm_module.to_latlon(
                    x,
                    y,
                    zone_number=orig_zone[0],
                    zone_letter=orig_zone[1],
                    strict=False,
                )
            else:
                lat, lon = None, None

        if lat is not None:
            posmask = np.logical_or(lat > 84, lat < -84)
        else:
            fast = True
        inds = []
        dx = []

        xlist, ylist = self.xy()
        lonlist, latlist = self.lonlat()
        for (
            n,
            (xx, yy),
        ) in enumerate(zip(x, y)):
            dxx, ii = None, None
            if lat is None:  # No UTM zone set so only option to use cartesian check-up
                dxx, ii = distance_funcs.min_cartesian_distance(xx, yy, xlist, ylist)
            elif posmask[n]:  # Over 84 lat so using slow method even if fast requested
                if latlist is not None:
                    dxx, ii = distance_funcs.min_distance(
                        lon[n], lat[n], lonlist, latlist
                    )
            elif fast:
                dxx, ii = distance_funcs.min_cartesian_distance(xx, yy, xlist, ylist)
            else:
                if latlist is not None:
                    dxx, ii = distance_funcs.min_distance(
                        lon[n], lat[n], lonlist, latlist
                    )
            if dxx is not None:
                inds.append(ii)
                dx.append(dxx)
        self.utm.set(orig_zone, silent=True)  # Reset UTM zone

        if unique:
            inds = np.unique(inds)

        if self.is_gridded():
            inds_x = []
            inds_y = []
            for ind in inds:
                indy, indx = np.unravel_index(ind, self.size())
                inds_x.append(indx)
                inds_y.append(indy)
            return {
                "inds_x": np.array(inds_x),
                "inds_y": np.array(inds_y),
                "dx": np.array(dx),
            }
        else:
            return {"inds": np.array(inds), "dx": np.array(dx)}

    def activate_dask(
        self, chunks="auto", primary_dim: str = None, rechunk: bool = True
    ) -> None:
        self.chunks = chunks
        if rechunk:
            self.rechunk(chunks, primary_dim)

    def deactivate_dask(self, dechunk: bool = False) -> None:
        """Deactivates the use of dask, meaning:

        1) Data will not be converted to dask-arrays when set, unless chunks provided
        2) Data will be converted from dask-arrays to numpy arrays when get
        3) All data will be converted to numpy arrays if unchunk=True"""
        self.chunks = None

        if dechunk:
            self._dechunk()

    def rechunk(
        self,
        chunks: Union[tuple, dict, str] = "auto",
        primary_dim: Union[str, list[str]] = None,
    ) -> None:
        if self.chunks is None:
            raise ValueError(
                "Dask mode is not activated! use .activate_dask() before rechunking"
            )
        if primary_dim:
            if isinstance(primary_dim, str):
                primary_dim = [primary_dim]
            chunks = {}
            for dim in primary_dim:
                chunks[dim] = len(self.get(dim))

        if isinstance(chunks, dict):
            chunks = self._chunk_tuple_from_dict(chunks)
        self.chunks = chunks
        dask_manager = DaskManager(self.chunks)
        for var in self.core.data_vars():
            data = self.get(var)
            if data is not None:
                self.set(var, dask_manager.dask_me(data, chunks))
        for var in self.core.masks():
            data = self.get(var)
            if data is not None:
                self.set(var, dask_manager.dask_me(data, chunks))

    def _dechunk(self) -> None:
        """Computes all dask arrays and coverts them to numpy arrays.

        If data is big this might taka a long time or kill Python."""
        dask_manager = DaskManager()
        for var in self.core.data_vars():
            data = self.get(var)
            if data is not None:
                self.set(var, dask_manager.undask_me(data))
        for var in self.core.masks():
            data = self.get(var)
            if data is not None:
                self.set(var, dask_manager.undask_me(data))

    def dask(self) -> bool:
        return self.chunks is not None

    @property
    def name(self) -> str:
        if not hasattr(self, "_name"):
            return "LonelySkeleton"
        return self._name

    @name.setter
    def name(self, new_name):
        if isinstance(new_name, str):
            self._name = new_name
        else:
            raise ValueError("name needs to be a string")

    def _chunk_tuple_from_dict(self, chunk_dict: dict) -> tuple[int]:
        """Determines a tuple of chunks based on a dict of coordinates and chunks"""
        chunk_list = []
        for coord in self.core.coords():
            chunk_list.append(chunk_dict.get(coord, "auto"))
        return tuple(chunk_list)

    def iterate(self, coords: list[str] = None):
        coords = coords or self.core.coords("grid")
        return iter(self)(coords)

    def __iter__(self):
        coords_dict = {coord: self.get(coord) for coord in self.core.coords("all")}
        return SkeletonIterator(
            coords_dict,
            self.core.coords("grid"),
            self,
        )

    def __repr__(self) -> str:
        def string_of_coords(list_of_coords) -> str:
            if not list_of_coords:
                return ""
            string = "("
            for c in list_of_coords:
                string += f"{c}, "
            string = string[:-2]
            string += ")"
            return string

        string = f"<{type(self).__name__} ({self.__class__.__base__.__name__})>\n"

        string += f"{' Coordinate groups ':-^80}" + "\n"
        string += f"{'Spatial:':12}"

        string += string_of_coords(self.core.coords("spatial")) or "*empty*"
        string += f"\n{'Grid:':12}"
        string += string_of_coords(self.core.coords("grid")) or "*empty*"
        string += f"\n{'Gridpoint:':12}"
        string += string_of_coords(self.core.coords("gridpoint")) or "*empty*"

        string += f"\n{'All:':12}"
        string += string_of_coords(self.core.coords("all")) or "*empty*"

        string += "\n" + f"{' Xarray ':-^80}" + "\n"
        string += self.ds().__repr__()

        empty_vars = self._ds_manager.empty_vars()
        empty_masks = self._ds_manager.empty_masks()

        if empty_masks or empty_vars:
            string += "\n" + f"{' Empty data ':-^80}"

            if empty_vars:
                string += "\n" + "Empty variables:"
                max_len = len(max(empty_vars, key=len))
                for var in empty_vars:
                    string += f"\n    {var:{max_len+2}}"
                    string += string_of_coords(
                        self.core.coords(self.core.coord_group(var))
                    )
                    string += f":  {self.core.default_value(var)}"
                    meta_parameter = self.core.meta_parameter(var)
                    if meta_parameter is not None:
                        string += f" [{meta_parameter.unit()}]"
                        string += f" {meta_parameter.standard_name()}"

            if empty_masks:
                string += "\n" + "Empty masks:"
                max_len = len(max(empty_masks, key=len))
                for mask in empty_masks:
                    string += f"\n    {mask:{max_len+2}}"
                    string += string_of_coords(
                        self.core.coords(self.core.coord_group(mask))
                    )
                    string += f":  {bool(self.core.default_value(mask))}"

        magnitudes = self.core.magnitudes()

        if magnitudes:
            string += "\n" + f"{' Magnitudes and directions ':-^80}"
            for key in magnitudes:
                value = self.core.get(key)
                string += f"\n  {key}: magnitude of ({value.x},{value.y})"

                meta_parameter = self.core.meta_parameter(key)
                if meta_parameter is not None:
                    string += f" [{meta_parameter.unit()}]"
                    string += f" {meta_parameter.standard_name()}"

        directions = self.core.directions()
        if directions:
            for key in directions:
                value = self.core.get(key)
                string += f"\n  {key}: direction of ({value.x},{value.y})"
                meta_parameter = self.core.meta_parameter(key)
                if meta_parameter is not None:
                    string += f" [{meta_parameter.unit()}]"
                    string += f" {meta_parameter.standard_name()}"

        string += "\n" + "-" * 80

        return string
