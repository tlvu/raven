import six
import datetime as dt
import collections
from pathlib import Path
from xclim.utils import units
from xclim.utils import units2pint

# Can be removed when xclim is pinned above 0.14
units.define("deg_C = degC")

"""
Raven configuration
-------------------

The RV class is used to store Raven parameters for emulated models.

Each model should subclass RV to define the parameters it expects using a namedtuple class. For example::

    class MyModel(RV):
        params = namedtuple('ModelParams', 'x1, x2, x3')
        init = namedtuple('ModelInit', 'i1, i2')
        hru = namedtuple('ModelHRU', 'hru1', hru2')

It can then be instantiated by passing values that will set as default values for each parameter::

    rv = MyModel(params=MyModel.params(1,2,3), init=MyModel.init(0,0), hru=MyModel.hru(4,5), name='basin')

values can then be modified either using attributes or properties::

    rv.name = 'LacVert'
    rv['evaluation_metrics'] = 'LOG_NASH'


Simulation end date and duration are updated automatically when duration, start date or end date are changed.

"""

default_input_variables = ("pr", "rainfall", "prsn", "tasmin", "tasmax", "tas", "evspsbl",
                           "water_volume_transport_in_river_channel")


class RVFile:

    def __init__(self, fn):
        self.fn = Path(fn)

        self.ext = ""
        self._store_ext()

        self.content = ""
        self._store_content()

    def _store_content(self):
        self.content = self.fn.read_text()

    def _store_ext(self):
        try:
            self.ext = self.fn.suffixes[0][1:]
        except IndexError as e:
            msg = "\nFile {} does not look like a valid Raven/Ostrich config file.".format(self.fn)
            raise ValueError(msg) from e

    @property
    def is_tpl(self):
        return self.fn.suffix in ['.tpl', '.txt']

    @property
    def stem(self):
        return Path(self.fn.stem).stem

    def write(self, path, **kwds):
        fn = path / self.fn.name

        content = self.content
        if kwds:
            content = content.format(**kwds)

        fn.write_text(content)
        return fn

    @property
    def tags(self):
        """Return a list of tags within the templates."""
        import re
        pattern = re.compile(r"{([\.\w]+)}")

        return pattern.findall(self.content)


class RV(collections.Mapping):
    """Generic configuration class.

    RV provides two mechanisms to set values, a dictionary-like interface and an object-like interface::

        rv = RV(a=None)
        rv['a'] = 1
        rv.a = 2

    The dictionary like interface only allows the modification of values for existing items, while the object interface
    allows the creation of new attributes::

      rv['c'] = 1

    will raise an AttributeError, while::

      rv.c = 1

    will create a new `c` attribute and assign it the value 1.

    """

    def __init__(self, **kwargs):
        # Set initial default values
        for key, val in kwargs.items():
            setattr(self, key, val)

    def __getitem__(self, key):
        return getattr(self, key)

    def __setitem__(self, key, value):
        if not hasattr(self, key):
            raise AttributeError('Trying to assign unrecognized object: {}'.format(key))

        setattr(self, key, value)

    def __len__(self):
        return len(self.__dict__)

    def __iter__(self):
        return iter(self.keys())

    def keys(self):
        return (key[1:] if key.startswith('_') else key for key in self.__dict__)

    def items(self):
        for attribute in self.keys():
            yield attribute, getattr(self, attribute)

    def update(self, items, force=False):
        """Update values from dictionary items.

        Parameters
        ----------
        items : dict
          Dictionary of values.
        force : bool
          If True, un-initialized keys can be set.
        """
        if force:
            for key, val in items.items():
                setattr(self, key, val)
        else:
            for key, val in items.items():
                self[key] = val


class RavenNcData(RV):
    pat = """
          :{kind} {raven_name} {site} {runits}
              :ReadFromNetCDF
                 :FileNameNC      {path}
                 :VarNameNC       {var_name}
                 :DimNamesNC      {dimensions}
                 :StationIdx      {index}
                 {time_shift}
                 {linear_transform}
              :EndReadFromNetCDF
          :End{kind}
          """

    _var_names = {'tasmin': "TEMP_MIN",
                  'tasmax': "TEMP_MAX",
                  'tas': "TEMP_AVE",
                  'rainfall': "RAINFALL",
                  'pr': "PRECIP",
                  'prsn': "SNOWFALL",
                  'evspsbl': "PET",
                  'water_volume_transport_in_river_channel': "HYDROGRAPH"
                  }

    _var_runits = {'tasmin': 'deg_C',
                   'tasmax': 'deg_C',
                   'tas': 'deg_C',
                   'pr': "mm/d",
                   'rainfall': "mm/d",
                   'prsn': "mm/d",
                   'evspsbl': "mm/d",
                   'water_volume_transport_in_river_channel': "m3/s"
                   }

    def __init__(self, **kwargs):
        self.var = None
        self.path = None
        self.var_name = None
        self.units = None
        self.scale_factor = None
        self.add_offset = None

        self._time_shift = None
        self._dimensions = None
        self._index = None
        self._linear_transform = None
        self._site = None
        self._kind = None
        self._runits = None
        self._raven_name = None
        self._site = None

        super().__init__(**kwargs)

    @property
    def raven_name(self):
        return self._var_names[self.var]

    @property
    def runits(self):
        return self._var_runits[self.var]

    @property
    def kind(self):
        if self.var == 'water_volume_transport_in_river_channel':
            return "ObservationData"
        else:
            return "Data"

    @property
    def site(self):
        if self.var == 'water_volume_transport_in_river_channel':
            return 1
        else:
            return ""

    @property
    def index(self):
        if self._index is not None:
            return str(self._index + 1)

    @index.setter
    def index(self, value):
        self._index = value

    @property
    def dimensions(self):
        """Return dimensions as Raven expects it:
        - time
        - station time
        - lon lat time
        """
        dims = list(self._dimensions)

        # Move the time dimension at the end
        dims.remove('time')
        dims.append('time')

        return ' '.join(dims)

    @dimensions.setter
    def dimensions(self, value):
        if 'time' not in value:
            raise ValueError("Raven expects a time dimension.")

        self._dimensions = value

        # If there is no spatial dimension, set the index to 0.
        if self.index is None and len(value) == 1:
            self._index = 0

    @property
    def time_shift(self):
        """The fraction describing the time shift, for example to convert UTC to local time."""
        if self._time_shift is not None:
            return f":TimeShift {self._time_shift}"

    @time_shift.setter
    def time_shift(self, value):
        self._time_shift = value

    @property
    def linear_transform(self):
        """A sequence of two values: multiplicative factor and additive offset."""
        lt = self._linear_transform
        if lt is not None or self.scale_factor is not None or self.add_offset is not None:
            slope, intercept = lt
            sf = 1 if self.scale_factor is None else self.scale_factor
            offset = 0 if self.add_offset is None else self.add_offset
            return ":LinearTransform {:g} {:g}".format(slope * sf, offset * slope + intercept)

    @linear_transform.setter
    def linear_transform(self, value):
        """Set the scale factor and offset."""
        if len(value) == 1:
            value = (value, 0)
        elif len(value) == 2:
            pass
        else:
            raise ValueError("Linear transform takes at most two values: "
                             "a scaling factor and an offset.")

        self._linear_transform = value

    def _check_units(self):
        import warnings
        if units2pint(self.units) != units2pint(self.runits):
            if self._linear_transform is None:
                warnings.warn(f"Units are not what Raven expects for {self.var}.\n"
                              f"Actual: {self.units}\n"
                              f"Expected: {self.runits}\n"
                              f"Make sure to set linear_transform to perform conversion."
                              )

    def __str__(self):
        if self.var is None:
            return ""
        else:
            kwds = {k: v if v is not None else "" for (k, v) in self.items()}
            return self.pat.format(**kwds)


class RVT(RV):
    def __init__(self, **kwargs):
        self._nc_index = None
        super(RVT, self).__init__(**kwargs)

    @property
    def nc_index(self):
        return self._nc_index

    @nc_index.setter
    def nc_index(self, value):
        for key, val in self.items():
            if isinstance(val, RavenNcData):
                setattr(val, 'index', value)

    def update(self, items, force=False):
        """Update values from dictionary items.

        Parameters
        ----------
        items : dict
          Dictionary of values.
        force : bool
          If True, un-initialized keys can be set.
        """
        if force:
            raise ValueError("Cannot add a new variable at run-time.")
        else:
            for key, val in items.items():
                if isinstance(val, dict):
                    self[key].update(val, force=True)


class RVI(RV):
    def __init__(self, **kwargs):
        self.name = None
        self.area = None
        self.elevation = None
        self.latitude = None
        self.longitude = None
        self.run_index = 0
        self.raven_version = '2.9 rev#177'

        self._run_name = 'run'
        self._start_date = None
        self._end_date = None
        self._now = None
        self._rain_snow_fraction = "RAINSNOW_DATA"
        self._duration = 1
        self._time_step = 1.0
        self._evaluation_metrics = 'NASH_SUTCLIFFE RMSE'
        self._suppress_output = False

        super(RVI, self).__init__(**kwargs)

    @property
    def run_name(self):
        return self._run_name

    @run_name.setter
    def run_name(self, x):
        if isinstance(x, six.string_types):
            self._run_name = x
        else:
            raise ValueError("Must be string")

    @property
    def start_date(self):
        return self._start_date

    @start_date.setter
    def start_date(self, x):
        if isinstance(x, dt.datetime):
            self._start_date = x
        else:
            raise ValueError("Must be datetime")

        if x != dt.datetime(1, 1, 1):
            self._update_duration()

    @property
    def end_date(self):
        return self._end_date

    @end_date.setter
    def end_date(self, x):
        if isinstance(x, dt.datetime):
            self._end_date = x
        else:
            raise ValueError("Must be datetime")

        if x != dt.datetime(1, 1, 1):
            self._update_duration()

    @property
    def duration(self):
        return self._duration

    @duration.setter
    def duration(self, x):
        if isinstance(x, int):
            if x > 0:
                self._duration = x
        else:
            raise ValueError("Must be int")

        if x > 0:
            self._update_end_date()

    @property
    def time_step(self):
        return self._time_step

    @time_step.setter
    def time_step(self, x):
        self._time_step = x

    @property
    def evaluation_metrics(self):
        return self._evaluation_metrics

    @evaluation_metrics.setter
    def evaluation_metrics(self, x):
        if not isinstance(x, six.string_types):
            raise ValueError("Evaluation metrics must be string.")

        for metric in x.split():
            if metric not in {'NASH_SUTCLIFFE', 'LOG_NASH', 'RMSE', 'PCT_BIAS', 'ABSERR', 'ABSMAX', 'PDIFF', 'TMVOL',
                              'RCOEFF', 'NSC', 'KLING_GUPTA'}:
                raise ValueError("{} is not a metric recognized by Raven.")

        self._evaluation_metrics = x

    def _update_duration(self):
        if self.end_date is not None and self.start_date is not None:
            self._duration = (self.end_date - self.start_date).days

    def _update_end_date(self):
        if self.start_date is not None and self.duration is not None:
            self._end_date = self.start_date + dt.timedelta(days=self.duration)

    @property
    def now(self):
        return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    @property
    def suppress_output(self):
        return ":SuppressOutput" if self._suppress_output else ""

    @suppress_output.setter
    def suppress_output(self, value):
        if not isinstance(value, bool):
            raise ValueError
        self._suppress_output = value

    @property
    def rain_snow_fraction(self):
        """Rain snow partitioning.
        """
        return self._rain_snow_fraction

    @rain_snow_fraction.setter
    def rain_snow_fraction(self, value):
        """Can be one of

        - RAINSNOW_DATA
        - RAINSNOW_DINGMAN
        - RAINSNOW_UBC
        - RAINSNOW_HBV
        - RAINSNOW_HARDER
        - RAINSNOW_HSPF
        """
        v = value.upper()
        options = ("RAINSNOW_DATA", "RAINSNOW_DINGMAN", "RAINSNOW_UBC", "RAINSNOW_HBV", "RAINSNOW_HARDER",
                 "RAINSNOW_HSPF")
        if v in options:
            self._rain_snow_fraction = v
        else:
            raise ValueError(f"Value should be one of {options}.")


class Ost(RV):
    def __init__(self, **kwargs):
        self._max_iterations = None
        self._random_seed = None

        super(Ost, self).__init__(**kwargs)

    @property
    def max_iterations(self):
        return self._max_iterations

    @max_iterations.setter
    def max_iterations(self, x):
        if x < 1:
            raise ValueError("Max iteration should be a positive integer: {}".format(x))
        else:
            self._max_iterations = x

    @property
    def random_seed(self):
        if self._random_seed is not None:
            return "RandomSeed {}".format(self._random_seed)
        return ""

    @random_seed.setter
    def random_seed(self, value):
        if value >= 0:
            self._random_seed = value
        else:
            self._random_seed = None


def isinstance_namedtuple(x):
    a = isinstance(x, tuple)
    b = getattr(x, '_fields', None) is not None
    return a and b


def guess_linear_transform(actual, expected):
    """Return RVT compatible dictionary for variable unit transformations.

    Parameters
    ----------
    actual : dict
      The units of each variable.
    expected : dict
      The units expected by Raven.

    Returns
    -------
    dict
      Dictionary keyed by <variable_name>_linear_transform, storing "<scale> <offset>"
      strings used by Raven to transform units.

    """
    # TODO : For precip we also need the frequency to sum over one day.
