import numpy as np
import pytest
from astropy import units as u
from astropy.time import Time
from roman_datamodels.datamodels import FlatRefModel, WfiImageModel

from romancal.flatfield import FlatFieldStep

RNG = np.random.default_rng(172)


@pytest.mark.parametrize(
    "instrument, exptype",
    [
        ("WFI", "WFI_IMAGE"),
    ],
)
def test_flatfield_step_interface(instrument, exptype):
    """Test that the basic inferface works for data requiring a FLAT reffile"""

    shape = (8, 20, 20)

    wfi_image_model = WfiImageModel.make_default(shape=shape)
    wfi_image_model.meta.instrument.name = instrument
    wfi_image_model.meta.instrument.detector = "WFI01"
    wfi_image_model.meta.instrument.optical_element = "F158"
    wfi_image_model.meta.exposure.type = exptype
    wfi_image_model.data = u.Quantity(
        np.ones(shape[1:], dtype=np.float32), u.electron / u.s, dtype=np.float32
    )
    wfi_image_model.dq = np.zeros(shape[1:], dtype=np.uint32)
    wfi_image_model.err = u.Quantity(
        np.zeros(shape[1:], dtype=np.float32), u.electron / u.s, dtype=np.float32
    )
    wfi_image_model.var_poisson = u.Quantity(
        np.zeros(shape[1:], dtype=np.float32),
        u.electron**2 / u.s**2,
        dtype=np.float32,
    )
    wfi_image_model.var_rnoise = u.Quantity(
        np.zeros(shape[1:], dtype=np.float32),
        u.electron**2 / u.s**2,
        dtype=np.float32,
    )
    wfi_image_model.var_flat = u.Quantity(
        np.zeros(shape[1:], dtype=np.float32),
        u.electron**2 / u.s**2,
        dtype=np.float32,
    )

    flatref_model = FlatRefModel.make_default(shape=shape)
    flatref_model.meta.optincal_element = "F158"
    flatref_model.meta.instrument.detector = "WFI01"
    flatref_model.data = np.ones(shape[1:], dtype=np.float32)
    flatref_model.dq = np.zeros(shape[1:], dtype=np.uint32)
    flatref_model.err = (RNG.uniform(size=shape[1:]) * 0.05).astype(np.float32)

    result = FlatFieldStep.call(wfi_image_model, override_flat=flatref_model)

    assert (result.data == wfi_image_model.data).all()
    assert result.var_flat.shape == shape[1:]
    assert result.meta.cal_step.flat_field == "COMPLETE"

    # test that the step is skipped if the reference file is N/A
    result = FlatFieldStep.call(wfi_image_model, override_flat="N/A")

    assert result.meta.cal_step.flat_field == "SKIPPED"


@pytest.mark.parametrize(
    "instrument, exptype",
    [
        ("WFI", "WFI_IMAGE"),
    ],
)
def test_crds_temporal_match(instrument, exptype):
    """Test that the basic inferface works for data requiring a FLAT reffile"""

    wfi_image_model = WfiImageModel.make_default()
    wfi_image_model.meta.instrument.name = instrument
    wfi_image_model.meta.instrument.detector = "WFI01"
    wfi_image_model.meta.instrument.optical_element = "F158"

    wfi_image_model.meta.exposure.start_time = Time("2020-01-02T11:11:11.110")
    wfi_image_model.meta.exposure.end_time = Time("2020-01-02T11:33:11.110")

    wfi_image_model.meta.exposure.type = exptype

    step = FlatFieldStep()
    ref_file_path = step.get_reference_file(wfi_image_model, "flat")

    wfi_image_model.meta.exposure.start_time = Time("2021-09-01T00:11:11.110")
    wfi_image_model.meta.exposure.end_time = Time("2021-09-01T00:33:11.110")
    ref_file_path_b = step.get_reference_file(wfi_image_model, "flat")
    assert "/".join(ref_file_path.rsplit("/", 1)[1:]) != "/".join(
        ref_file_path_b.rsplit("/", 1)[1:]
    )


@pytest.mark.parametrize(
    "instrument",
    [
        "WFI",
    ],
)
@pytest.mark.parametrize(
    "exptype",
    [
        "WFI_GRISM",
        "WFI_PRISM",
    ],
)
def test_spectroscopic_skip(instrument, exptype):
    wfi_image_model = WfiImageModel.make_default()
    wfi_image_model.meta.instrument.name = instrument
    wfi_image_model.meta.instrument.detector = "WFI01"
    wfi_image_model.meta.instrument.optical_element = "F158"

    wfi_image_model.meta.exposure.start_time = Time("2020-02-01T00:00:00.000")
    wfi_image_model.meta.exposure.end_time = Time("2020-02-01T00:00:05.000")

    wfi_image_model.meta.exposure.type = exptype

    result = FlatFieldStep.call(wfi_image_model)
    assert result.meta.cal_step.flat_field == "SKIPPED"
