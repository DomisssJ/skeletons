import dask.array as da
import xarray as xr
from typing import Union
import numpy as np


class DaskManager:
    def __init__(self, chunks="auto"):
        self.chunks = chunks

    @staticmethod
    def data_is_dask(data) -> bool:
        """Checks if a data array is a dask array"""
        return hasattr(data, "chunks") and data.chunks is not None

    def dask_me(self, data, chunks=None):
        """Convert a numpy array to a dask array if needed and wanted"""
        if self.data_is_dask(data):
            if chunks is not None:
                if not isinstance(data, xr.DataArray):
                    data = data.rechunk(chunks)
                else:
                    data.data = data.data.rechunk(chunks)

            return data

        chunks = chunks or self.chunks
        if not isinstance(data, xr.DataArray):
            return da.from_array(data, chunks=chunks)
        else:
            data.data = da.from_array(data.data, chunks=chunks)
            return data

    def undask_me(self, data):
        """Convert a dask array to a numpy array if needed"""
        if not self.data_is_dask(data):
            return data

        return data.compute()

    def constant_array(
        self, data, shape: tuple[int], dask: bool = True
    ) -> Union[da.array, np.array]:
        """Creates an dask or numpy array of a certain shape is given data is shapeless."""
        if isinstance(data, int) or isinstance(data, float) or isinstance(data, bool):
            if dask or self.data_is_dask(data):
                data = da.full(shape, data)
            else:
                data = np.full(shape, data)
        if data is not None and data.shape == ():
            if dask or self.data_is_dask(data):
                data = da.full(shape, data)
            else:
                data = np.full(shape, data)

        return data
