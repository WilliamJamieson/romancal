import os

import astropy.units as u
import numpy as np
import pytest
from astropy.modeling.models import Gaussian2D
from astropy.table import Table
from roman_datamodels.datamodels import MosaicModel

from romancal.datamodels import ModelLibrary
from romancal.multiband_catalog import MultibandCatalogStep


def make_test_image():
    g1 = Gaussian2D(121.0, 11.1, 12.2, 1.5, 1.5)
    g2 = Gaussian2D(70, 65, 18, 9.2, 4.5)
    g3 = Gaussian2D(111.0, 41, 42.7, 8.0, 3.0, theta=30 * u.deg)
    g4 = Gaussian2D(81.0, 17, 52.7, 4, 2, theta=102 * u.deg)
    g5 = Gaussian2D(107.0, 65, 71, 12, 2, theta=142 * u.deg)
    g6 = Gaussian2D(50, 20, 80, 2.1, 2.1)
    g7 = Gaussian2D(97.0, 85, 87.3, 4, 2, theta=-30 * u.deg)

    yy, xx = np.mgrid[0:101, 0:101]
    data = (
        g1(xx, yy)
        + g2(xx, yy)
        + g3(xx, yy)
        + g4(xx, yy)
        + g5(xx, yy)
        + g6(xx, yy)
        + g7(xx, yy)
    ).value.astype("float32")

    rng = np.random.default_rng(seed=123)
    noise = rng.normal(0, 2.5, size=data.shape)
    data += noise
    err = data / 10.0

    return data, err


@pytest.fixture
def mosaic_model():
    model = MosaicModel(shape=(2, 101, 101))
    data, err = make_test_image()
    model.data = data
    model.err = err
    model.var_rnoise = err**2
    model.weight = 1.0 / err
    return model


@pytest.fixture
def library_model(mosaic_model):
    model2 = mosaic_model.copy()
    model2.meta.basic.optical_element = "F184"
    return ModelLibrary([mosaic_model, model2])


@pytest.mark.webbpsf
@pytest.mark.parametrize(
    "snr_threshold, npixels, save_results",
    (
        (3, 10, True),
        (10, 10, False),
    ),
)
def test_multiband_catalog(
    library_model, snr_threshold, npixels, save_results, tmp_path
):
    os.chdir(tmp_path)
    step = MultibandCatalogStep()

    result = step.call(
        library_model,
        bkg_boxsize=50,
        snr_threshold=snr_threshold,
        npixels=npixels,
        fit_psf=False,
        save_results=save_results,
    )

    cat = result.source_catalog

    assert isinstance(cat, Table)

    columns = [
        "label",
        "xcentroid",
        "ycentroid",
        "ra_centroid",
        "dec_centroid",
        "is_extended",
        "sharpness",
        "roundness",
        "nn_label",
        "nn_dist",
        "isophotal_area",
        "semimajor_sigma",
        "semiminor_sigma",
        "ellipticity",
        "orientation",
        "sky_orientation",
        "ra_bbox_ll",
        "dec_bbox_ll",
        "ra_bbox_ul",
        "dec_bbox_ul",
        "ra_bbox_lr",
        "dec_bbox_lr",
        "ra_bbox_ur",
        "dec_bbox_ur",
    ]

    assert len(cat) == 7

    if len(cat) > 0:
        for col in columns:
            assert col in cat.colnames
        assert np.min(cat["xcentroid"]) > 0.0
        assert np.min(cat["ycentroid"]) > 0.0
        assert np.max(cat["xcentroid"]) < 100.0
        assert np.max(cat["ycentroid"]) < 100.0

        for phottype in ("isophotal", "kron", "aper30", "aper_total"):
            for filt in ("F158", "F184"):
                colname = f"{filt}_{phottype}_flux"
                assert colname in cat.colnames
                assert colname + "_err" in cat.colnames
