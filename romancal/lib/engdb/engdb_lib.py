"""Engineering DB common library."""

import abc
from collections import namedtuple

__all__ = ["EngDB_Value", "EngdbABC"]


# Define the returned value tuple.
EngDB_Value = namedtuple("EngDB_Value", ["obstime", "value"])

# Path templates
DATA = "_data.json"

# HTTP status that should get retries
# For statuses, just blanket cover the 4xx and 5xx errors
# However, do immediately fail for 404.
FORCE_STATUSES = list(range(400, 404)) + list(range(405, 460)) + list(range(500, 520))
RETRIES = 10
TIMEOUT = 10 * 60  # 10 minutes


class EngdbABC(abc.ABC):
    """
    Access the Roman Engineering Database.

    This is the minimal API for the service definition. Concrete implementations
    may provide other parameters and attributes.

    Parameters
    ----------
    **service_kwargs : dict
        Service-specific keyword arguments. Refer to the concrete implementations
        of EngdbABC.
    """

    @property
    @abc.abstractmethod
    def endtime(self):
        """The endtime of the search."""
        pass

    @property
    @abc.abstractmethod
    def response(self):
        """The `requests.Response` information."""
        pass

    @property
    @abc.abstractmethod
    def starttime(self):
        """The start time of the search."""
        pass

    @abc.abstractmethod
    def __init__(self, **service_kwargs):
        pass

    @abc.abstractmethod
    def get_meta(self, mnemonic="", **service_kwargs):
        """
        Get the mnemonics meta info.

        Parameters
        ----------
        mnemonic : str
            The engineering mnemonic to retrieve.

        Returns
        -------
        meta : object
            The meta information. Type of return is dependent on the type of service.

        service_kwargs : dict
            Service-specific keyword arguments. Refer to the concrete implementations
            of EngdbABC.
        """
        pass

    @abc.abstractmethod
    def get_values(
        self,
        mnemonic,
        starttime,
        endtime,
        time_format=None,
        include_obstime=False,
        include_bracket_values=False,
        zip_results=True,
    ):
        """
        Retrieve all results for a mnemonic in the requested time range.

        Parameters
        ----------
        mnemonic : str
            The engineering mnemonic to retrieve.

        starttime : str or `astropy.time.Time`
            The, inclusive, start time to retrieve from.

        endtime : str or `astropy.time.Time`
            The, inclusive, end time to retrieve from.

        time_format : str
            The format of the input time used if the input times
            are strings. If None, a guess is made.

        include_obstime : bool
            If `True`, the return values will include observation
            time as `astropy.time.Time`. See `zip_results` for further details.

        include_bracket_values : bool
            The DB service, by default, returns the bracketing
            values outside of the requested time. If `True`, include
            these values.

        zip_results : bool
            If `True` and `include_obstime` is `True`, the return values
            will be a list of 2-tuples. If false, the return will
            be a single 2-tuple, where each element is a list.

        Returns
        -------
        values : [value, ...] or [(obstime, value), ...] or ([obstime,...], [value, ...])
            Returns the list of values. See `include_obstime` and `zip_results` for modifications.

        Raises
        ------
        requests.exceptions.HTTPError
            Either a bad URL or non-existent mnemonic.
        """
        pass


class ValueCollection:
    """
    Engineering Value Collection.

    Parameters
    ----------
    include_obstime : bool
        If `True`, the return values will include observation
        time as `astropy.time.Time`. See `zip_results` for further details.

    zip_results : bool
        If `True` and `include_obstime` is `True`, the return values
        will be a list of 2-tuples. If false, the return will
        be a single 2-tuple, where each element is a list.

    Attributes
    ----------
    collection : [value, ...] or [(obstime, value), ...] or ([obstime,...], [value, ...])
        Returns the list of values.
        See `include_obstime` and `zip_results` for modifications.
    """

    def __init__(self, include_obstime=False, zip_results=True):
        self._include_obstime = include_obstime
        self._zip_results = zip_results
        if zip_results:
            self.collection = []
        else:
            self.collection = EngDB_Value([], [])

    def append(self, obstime, value):
        """
        Append value to collection.

        Parameters
        ----------
        obstime : `astropy.time.Time`
            Observation time as returned from the engineering.

        value : numeric
            Value from DB.
        """
        # Make all the times readable
        obstime.format = "isot"

        # Append
        if self._include_obstime:
            if self._zip_results:
                self.collection.append(EngDB_Value(obstime, value))
            else:
                self.collection.obstime.append(obstime)
                self.collection.value.append(value)
        else:
            self.collection.append(value)


def mnemonic_data_fname(mnemonic):
    """
    Construct the file name for the cached data of the specified mnemonic.

    Parameters
    ----------
    mnemonic : str
        The mnemonic to refer to.

    Returns
    -------
    file_name: str
        The name of the file containing the mnemonic's cached data.
    """
    return mnemonic.lower() + DATA
