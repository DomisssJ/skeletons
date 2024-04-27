import numpy as np
import xarray as xr
from .coordinate_manager import (
    CoordinateManager,
    SPATIAL_COORDS,
    move_time_and_spatial_to_front,
)

from ..errors import (
    DataWrongDimensionError,
    UnknownCoordinateError,
    CoordinateWrongLengthError,
    GridError,
)

import dask


class DatasetManager:
    """Contains methods related to the creation and handling of the Xarray
    Dataset that will be used in any object that inherits from Skeleton."""

    def __init__(self, coordinate_manager: CoordinateManager) -> None:
        self.coord_manager = coordinate_manager

    def create_structure(self, x, y, new_coords):
        """Create a Dataset containing only the relevant coordinates."""
        existing_coords = {
            c: self.get(c, strict=True) for c in self.coord_manager.coords("nonspatial")
        }
        # Updating dicts cause problems if one has a key that is explicitly value None
        given_coords = existing_coords
        for key in new_coords:
            given_coords[key] = new_coords.get(key, given_coords.get(key))

        coord_dict = self.create_coord_dict_from_input(
            x=x, y=y, given_coords=given_coords
        )
        var_dict = self.create_var_dict_from_input(x=x, y=y, coord_dict=coord_dict)
        self.set_new_ds(xr.Dataset(coords=coord_dict, data_vars=var_dict))

    def create_coord_dict_from_input(self, x, y, given_coords) -> dict:
        """Creates dictonary of the coordinates to be used for initializing the dataset"""

        coord_dict = {}

        if "inds" in self.coord_manager.coords("spatial"):
            coord_dict["inds"] = np.arange(len(x))
        else:
            coord_dict[self.coord_manager.y_str] = y
            coord_dict[self.coord_manager.x_str] = x

        # Add in other possible coordinates that are set at initialization
        for key in self.coord_manager.coords("nonspatial"):
            value = given_coords.get(key)

            if value is None:
                raise UnknownCoordinateError(
                    f"Skeleton has coordinate '{key}', but it was not provided: {list(given_coords.keys())}!"
                )
            coord_dict[key] = np.array(value)

        coord_dict = {
            c: coord_dict[c] for c in move_time_and_spatial_to_front(list(coord_dict))
        }

        return coord_dict

    def create_var_dict_from_input(self, x, y, coord_dict) -> dict:
        """Creates dictionary of variables"""
        var_dict = {}
        initial_vars = self.coord_manager.data_vars("spatial")
        initial_x = "x" if "x" in initial_vars else "lon"
        initial_y = "y" if "y" in initial_vars else "lat"

        if initial_y in initial_vars:
            coord_group = self.coord_manager.get(initial_y).coord_group
            coords = self.coord_manager.coords(coord_group)
            if not coords <= list(coord_dict.keys()):
                raise ValueError(
                    f"Trying to make variable '{initial_y}' depend on {coords}, but it is not set as a coordinate ({list(coord_dict.keys())}!"
                )
            var_dict[self.coord_manager.y_str] = (coords, y)
        if initial_x in initial_vars:
            coord_group = self.coord_manager.get(initial_x).coord_group
            coords = self.coord_manager.coords(coord_group)
            if not coords <= list(coord_dict.keys()):
                raise ValueError(
                    f"Trying to make variable '{initial_x}' depend on {coords}, but it is not set as a coordinate ({list(coord_dict.keys())}!"
                )
            var_dict[self.coord_manager.x_str] = (coords, x)

        return var_dict

    def set_new_ds(self, ds: xr.Dataset) -> None:
        self.data = ds

    def ds(self):
        """Resturns the Dataset (None if doesn't exist)."""
        if not hasattr(self, "data"):
            return None
        return self.data

    def set(self, data: np.ndarray, name: str) -> None:
        """Adds in new data to the Dataset."""
        all_metadata = self.get_attrs()
        # self._merge_in_ds(self.compile_to_ds(data, name))
        self.data[name] = self.compile_data_array(data, name)
        for var, metadata in all_metadata.items():
            if var == "_global_":
                self.set_attrs(metadata)
            else:
                self.set_attrs(metadata, var)

    def empty_vars(self) -> list[str]:
        """Get a list of empty variables"""
        empty_vars = []
        for var in self.coord_manager.data_vars():
            if self.get(var) is None:
                empty_vars.append(var)
        return empty_vars

    def empty_masks(self) -> list[str]:
        """Get a list of empty masks"""
        empty_masks = []
        for mask in self.coord_manager.masks():
            if self.get(mask) is None:
                empty_masks.append(mask)
        return empty_masks

    def get(
        self,
        name: str,
        empty: bool = False,
        strict: bool = True,
        **kwargs,
    ) -> xr.DataArray:
        """Gets data from Dataset.

        **kwargs can be used for slicing data.

        """
        ds = self.ds()
        if ds is None:
            return None

        data = ds.get(name)
        if data is None:
            if strict:
                return None
            else:
                empty = True

        if empty:
            obj = self.coord_manager.get(name)
            if obj is None or obj.coord_group is None:
                return None
            coords = self.coord_manager.coords(obj.coord_group)

            empty_data = dask.array.full(
                self.coords_to_size(coords),
                obj.default_value,
            )

            coords_dict = {coord: self.get(coord) for coord in coords}
            data = xr.DataArray(data=empty_data, coords=coords_dict)

        return self._slice_data(data, **kwargs)

    def get_attrs(self) -> dict:
        """Gets a dictionary of all the data variable and global atributes.
        General attributes has key '_global_'"""
        meta_dict = {}
        meta_dict["_global_"] = self.data.attrs

        for var in self.data.data_vars:
            meta_dict[var] = self.data.get(var).attrs

        return meta_dict

    def set_attrs(self, attributes: dict, data_array_name: str = None) -> None:
        """Sets attributes to DataArray da_name.

        If data_array_name is not given, sets global attributes
        """
        if data_array_name is None:
            self.data.attrs = attributes
        else:
            self.data.get(data_array_name).attrs = attributes

    def _slice_data(self, data, **kwargs) -> xr.DataArray:
        coordinates = {}
        keywords = {}
        for key, value in kwargs.items():
            if key in list(data.coords):
                coordinates[key] = value
            else:
                keywords[key] = value

        for key, value in coordinates.items():
            # data = eval(f"data.sel({key}={value}, **keywords)")
            data = data.sel({key: value}, **keywords)

        return data

    def _merge_in_ds(self, ds_list: list[xr.Dataset]) -> None:
        """Merge in Datasets with some data into the existing Dataset of the
        Skeleton.
        """
        if not isinstance(ds_list, list):
            ds_list = [ds_list]
        for ds in ds_list:
            self.set_new_ds(ds.merge(self.ds(), compat="override"))

    def compile_data_array(self, data: np.ndarray, name: str) -> xr.DataArray:
        if name in self.coord_manager.coords("all"):
            # E.g. 'lon' should only depend on dim 'lon', not ['lat','lon']
            coord_dict = {name: ([name], data)}
        else:
            coord_group = self.coord_manager.coord_group(name)
            coords = self.coord_manager.coords(coord_group)
            coord_dict = {coord: ([coord], self.get(coord).data) for coord in coords}

        daa = xr.DataArray(data=data, coords=coord_dict)
        daa.name = name
        return daa

    # def compile_to_ds(self, data: np.ndarray, name: str) -> xr.Dataset:
    #     """This is used to compile a Dataset containing the given data using the
    #     coordinates of the Skeleton.
    #     """
    #     coord_group = self.coord_manager.coord_group(name)
    #     coords = self.coord_manager.coords(coord_group)
    #     coords_dict = {coord: self.get(coord) for coord in coords}

    #     coord_shape = self.coords_to_size(coords)
    #     if coord_shape != data.shape:
    #         raise DataWrongDimensionError(
    #             data_shape=data.shape, coord_shape=coord_shape
    #         )

    #     vars_dict = {name: (coords_dict.keys(), data)}
    #     ds = xr.Dataset(data_vars=vars_dict, coords=coords_dict)
    #     return ds

    def coords_to_size(self, coords: list[str], **kwargs) -> tuple[int]:
        list = []
        data = self._slice_data(self.ds(), **kwargs)
        for coord in coords:
            list.append(len(data.get(coord)))

        return tuple(list)
