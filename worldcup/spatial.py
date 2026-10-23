"""Shared H3 mapping so the worker UDF and local checks use one function."""


def latlon_to_h3(lat: float, lon: float, resolution: int) -> str:
    import h3

    return h3.latlng_to_cell(lat, lon, resolution)
