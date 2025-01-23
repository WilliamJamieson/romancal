"""Ramp Fitting tests involving MultiAccum Tables"""

import numpy as np
import pytest
from astropy.time import Time
from roman_datamodels.datamodels import (
    DarkRefModel,
    GainRefModel,
    RampModel,
    ReadnoiseRefModel,
)

from romancal.ramp_fitting import RampFitStep

# Read Time in seconds
#   For Roman, the read time of the detectors is a fixed value and is currently
#   backed into code. Will need to refactor to consider the more general case.
#   Used to deconstruct the MultiAccum tables into integration times.
ROMAN_READ_TIME = 3.04

rng = np.random.default_rng(42)

# Basic resultant
#
# The read pattern is `[[1], [2], [3], [4]]`
# The total expected counts is 7.
# The resultants were generated with
# `romanisim.l1.apportion_counts_to_resultants(counts, read_pattern)`.
SIMPLE_RESULTANTS = np.array(
    [
        [[2.0, 2.0], [5.0, 1.0]],
        [[4.0, 5.0], [6.0, 2.0]],
        [[5.0, 6.0], [7.0, 6.0]],
        [[7.0, 7.0], [7.0, 7.0]],
    ],
    dtype=np.float32,
)
SIMPLE_EXPECTED_DEFAULT = {
    "data": np.array(
        [[0.52631587, 0.52631587], [0.23026317, 0.7236843]], dtype=np.float32
    ),
    "err": np.array(
        [[0.24262409, 0.24262409], [0.16048454, 0.28450054]], dtype=np.float32
    ),
    "var_poisson": np.array(
        [[0.05886428, 0.05886428], [0.02575312, 0.08093839]], dtype=np.float32
    ),
    "var_rnoise": np.array(
        [[2.164128e-06, 2.164128e-06], [2.164128e-06, 2.164128e-06]], dtype=np.float32
    ),
}
SIMPLE_EXPECTED_GAIN = {
    "data": np.array([[0.526316, 0.526316], [0.230263, 0.701852]], dtype=np.float32),
    "err": np.array([[0.108513, 0.108513], [0.071783, 0.124624]], dtype=np.float32),
    "var_poisson": np.array(
        [[1.1772858e-02, 1.1772858e-02], [5.150624e-03, 1.55289e-02]], dtype=np.float32
    ),
    "var_rnoise": np.array(
        [[2.164127e-06, 2.164127e-06], [2.164127e-06, 2.190606e-06]], dtype=np.float32
    ),
}
SIMPLE_EXPECTED_RNOISE = {
    "data": np.array(
        [[0.52631587, 0.52631587], [0.23026317, 0.7236843]], dtype=np.float32
    ),
    "err": np.array([[14.712976, 14.712976], [14.711851, 14.713726]], dtype=np.float32),
    "var_poisson": np.array(
        [[0.05886428, 0.05886428], [0.02575312, 0.08093839]], dtype=np.float32
    ),
    "var_rnoise": np.array(
        [[216.4128, 216.4128], [216.4128, 216.4128]], dtype=np.float32
    ),
}


# #####
# Tests
# #####
def test_bad_readpattern():
    """Ensure error is raised on bad readpattern"""
    ramp_model, gain_model, readnoise_model, dark_model = make_data(
        SIMPLE_RESULTANTS, 1, 0.01, False
    )
    bad_pattern = ramp_model.meta.exposure.read_pattern.data[1:]
    ramp_model.meta.exposure.read_pattern = bad_pattern

    with pytest.raises(RuntimeError):
        RampFitStep.call(
            ramp_model,
            algorithm="ols_cas22",
            override_gain=gain_model,
            override_readnoise=readnoise_model,
            override_dark=dark_model,
        )


@pytest.mark.parametrize(
    "attribute",
    ["data", "err", "var_poisson", "var_rnoise"],
    ids=["data", "err", "var_poisson", "var_rnoise"],
)
def test_fits(fit_ramps, attribute):
    """Check slopes"""
    image_model, expected = fit_ramps

    value = getattr(image_model, attribute)
    np.testing.assert_allclose(value, expected[attribute], 1e-05)


# ########
# Fixtures
# ########
@pytest.fixture(
    scope="module",
    params=[
        pytest.param(
            (SIMPLE_RESULTANTS, 1, 0.01, False, SIMPLE_EXPECTED_DEFAULT, False),
            id="default",
        ),  # No gain or noise
        pytest.param(
            (SIMPLE_RESULTANTS, 5, 0.01, False, SIMPLE_EXPECTED_GAIN, False),
            id="extragain",
        ),  # Increase gain
        pytest.param(
            (SIMPLE_RESULTANTS, 1, 100.0, False, SIMPLE_EXPECTED_RNOISE, False),
            id="extranoise",
        ),  # Increase noise
        pytest.param(
            (SIMPLE_RESULTANTS, 1, 0.01, False, SIMPLE_EXPECTED_DEFAULT, True),
            id="default-jump",
        ),  # No gain or noise
        pytest.param(
            (SIMPLE_RESULTANTS, 5, 0.01, False, SIMPLE_EXPECTED_GAIN, True),
            id="extragain-jump",
        ),  # Increase gain
        pytest.param(
            (SIMPLE_RESULTANTS, 1, 100.0, False, SIMPLE_EXPECTED_RNOISE, True),
            id="extranoise-jump",
        ),  # Increase noise
    ],
)
def fit_ramps(request):
    """Test ramp fits"""
    resultants, ingain, rnoise, randomize, expected, use_jump = request.param
    ramp_model, gain_model, readnoise_model, dark_model = make_data(
        resultants, ingain, rnoise, randomize
    )

    out_model = RampFitStep.call(
        ramp_model,
        algorithm="ols_cas22",
        use_ramp_jump_detection=use_jump,
        override_gain=gain_model,
        override_readnoise=readnoise_model,
        override_dark=dark_model,
    )

    return out_model, expected


# #########
# Utilities
# #########
def make_data(resultants, ingain, rnoise, randomize):
    """Create test input data

    Parameters
    ----------
    resultants : numpy.array.shape(3, xdim, ydim)
        The resultant array.

    ingain : int
        Gain to apply

    rnoise : float
        Noise to apply

    randomize : bool, expected)
        Randomize the gain and read noise across pixels.

    Returns
    -------
    image, gain, readnoise : ImageModel, GainRefModel, ReadnoiseRefModel.array
        Input image and related references
    """
    ramp_model = model_from_resultants(resultants)
    gain_model, readnoise_model, dark_model = generate_wfi_reffiles(
        ramp_model.shape[1:], ingain=ingain, rnoise=rnoise, randomize=randomize
    )

    return ramp_model, gain_model, readnoise_model, dark_model


def model_from_resultants(resultants, read_pattern=None):
    """Create a RampModel from resultants

    Parameters
    ----------
    resultants : numpy.array.shape(reads, xdim, ydim)
        The resultants to fit.

    read_pattern : [[int[,...]][,...]]
        The read pattern used to produce the resultants.
        If None, presume a basic read pattern
    """
    if read_pattern is None:
        read_pattern = [[idx + 1] for idx in range(resultants.shape[0])]

    # Full WFI image has reference pixels all around. Add those on.
    nrefpixs = 4
    full_wfi = np.ones(
        (
            resultants.shape[0],
            resultants.shape[1] + (nrefpixs * 2),
            resultants.shape[2] + (nrefpixs * 2),
        ),
        dtype=np.float32,
    )
    full_wfi[:, nrefpixs:-nrefpixs, nrefpixs:-nrefpixs] = resultants
    shape = full_wfi.shape

    pixdq = np.zeros(shape=shape[1:], dtype=np.uint32)
    err = np.zeros(shape=shape, dtype=np.float32)
    gdq = np.zeros(shape=shape, dtype=np.uint8)

    ramp_model = RampModel(_array_shape=shape)
    ramp_model.data = full_wfi
    ramp_model.pixeldq = pixdq
    ramp_model.groupdq = gdq
    ramp_model.err = err

    ramp_model.meta.exposure.frame_time = ROMAN_READ_TIME
    ramp_model.meta.exposure.nresultants = shape[0]

    ramp_model.meta.exposure.read_pattern = read_pattern

    return ramp_model


def generate_wfi_reffiles(
    shape, ingain=6, rnoise=0.01, darkcurrent=0.01, randomize=True
):
    """Create GainRefModel and ReadnoiseRefModel

    Parameters
    ----------
    shape : tuple
        Shape of the arrays

    ingain : float
        Maximum gain.

    rnoise : flota
        Maximum noise

    darkcurrent : float
        Dark current scale

    randomize : bool
        Randomize the gain and read noise data.
    """
    # Create temporary gain reference file
    gain_ref_model = GainRefModel(_array_shape=shape)

    gain_ref_model.meta.useafter = Time("2022-01-01T11:11:11.111")

    if randomize:
        gain_ref_model.data = (rng.random(shape) * 0.5).astype(np.float32) * ingain
    else:
        gain_ref_model.data = np.ones(shape).astype(np.float32) * ingain

    # TODO dq and error are not part of the schema for gain
    gain_ref_model["dq"] = np.zeros(shape, dtype=np.uint16)
    gain_ref_model["err"] = (rng.random(shape) * 0.05).astype(np.float32)

    # Create temporary readnoise reference file
    rn_ref_model = ReadnoiseRefModel(_array_shape=shape)
    rn_ref_model.meta.useafter = Time("2022-01-01T11:11:11.111")

    # TODO frame_time is not part of the schema for ref_exposure_type
    rn_ref_model.meta.exposure["frame_time"] = 666

    if randomize:
        rn_ref_model.data = ((rng.random(shape) * rnoise).astype(np.float32),)
    else:
        rn_ref_model.data = np.ones(shape).astype(np.float32) * rnoise

    # Create temporary dark reference file
    # shape needs to be 3D but does not matter because the ramp fitting
    # step only uses the 2-D dark slope component
    dark_ref_model = DarkRefModel(_array_shape=(1, *shape))
    dark_ref_model.meta.useafter = Time("2022-01-01T11:11:11.111")

    # TODO frame_time is not part of the schema for ref_exposure_type
    dark_ref_model.meta.exposure["frame_time"] = 666

    dark_ref_model.dark_slope = np.zeros(shape).astype(np.float32) * 0.01

    # return gainfile, readnoisefile
    return gain_ref_model, rn_ref_model, dark_ref_model
