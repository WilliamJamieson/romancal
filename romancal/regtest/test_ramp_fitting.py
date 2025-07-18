"""Module to test rampfit with optional output

Notes
-----
A requirement for the larger mission verification project is to have
tests tied to reqirements.
"""

from pathlib import Path

import pytest
import roman_datamodels as rdm

from romancal.lib.suffix import replace_suffix
from romancal.ramp_fitting import RampFitStep

from .regtestdata import compare_asdf


def log_result(requirement, message, result, logger):
    """Log individual test results that relate to a requirement

    Parameters
    ----------
    requirement : str
        The requirement being logged. I.e "DMS363"

    message : str
        Message describing what is being tested

    result : bool
        The result of the test
    """
    result_text = "PASS" if result else "FAIL"
    log_msg = f"{requirement} MSG: {message}.......{result_text}"
    logger.info(log_msg)


# ##########
# Conditions
# ##########
def cond_is_asdf(requirement, model, expected_path, logger):
    """Check that the filename has the correct file type"""
    msg = 'Testing that result file path has file type "asdf"'
    result = expected_path.exists() and expected_path.suffix == ".asdf"
    log_result(requirement, msg, result, logger)
    assert result, msg


def cond_is_imagemodel(requirement, model, expected_path, logger):
    """Check that the result is an ImageModel"""
    msg = "Testing that the result model is Level 2"
    result = isinstance(model, rdm.datamodels.ImageModel)
    log_result(requirement, msg, result, logger)
    assert result, msg


def cond_is_rampfit(requirement, model, expected_path, logger):
    """Check that the calibration suffix is 'rampfit'"""
    msg = 'Testing that the result file has the suffix "rampfit"'
    result = expected_path.exists() and expected_path.stem.endswith("rampfit")
    log_result(requirement, msg, result, logger)
    assert result, msg


def cond_is_step_complete(requirement, model, expected_path, logger):
    """Check that the calibration step is marked complete"""
    msg = "Testing that RampFitStep completed"
    result = model.meta.cal_step.ramp_fit == "COMPLETE"
    log_result(requirement, msg, result, logger)
    assert result, msg


def cond_is_truncated(requirement, model, expected_path, logger):
    """Check if the data represents a truncated MA table/read pattern"""
    msg = "Testing if data represents a truncated MA table"
    result = model.meta.exposure.truncated
    log_result(requirement, msg, result, logger)
    assert result, msg


def cond_is_uneven(requirement, model, expected_path, logger):
    """Verify that the provided model represents uneven ramps"""
    msg = "Testing that the ramps are uneven"
    length_set = {len(resultant) for resultant in model.meta.exposure.read_pattern}
    result = len(length_set) > 1
    log_result(requirement, msg, result, logger)
    assert result, msg


def cond_science_verification(
    requirement, model, expected_path, rtdata_module, ignore_asdf_paths, logger
):
    """Check against expected data results"""
    msg = "Testing science veracity"
    diff = compare_asdf(rtdata_module.output, rtdata_module.truth, **ignore_asdf_paths)

    result = diff.identical
    log_result(requirement, msg, result, logger)
    assert result, diff.report()


CONDITIONS_FULL = [
    cond_is_asdf,
    cond_is_imagemodel,
    cond_is_rampfit,
    cond_is_step_complete,
    cond_is_uneven,
]
CONDITIONS_TRUNC = [*CONDITIONS_FULL, cond_is_truncated]


# ######################
# fixtures and utilities
# ######################
@pytest.fixture(
    scope="module",
    params=[
        (
            "DMS362",
            Path("WFI/image/r0000101001001001001_0001_wfi01_f158_darkcurrent.asdf"),
            CONDITIONS_FULL,
        ),
        (
            "DMS366",
            Path("WFI/grism/r0000201001001001001_0001_wfi01_grism_darkcurrent.asdf"),
            CONDITIONS_FULL,
        ),
        (
            "DMS363",
            Path("WFI/image/r0000101001001001001_0003_wfi01_f158_darkcurrent.asdf"),
            CONDITIONS_TRUNC,
        ),
        (
            "DMS367",
            Path("WFI/grism/r0000201001001001001_0003_wfi01_grism_darkcurrent.asdf"),
            CONDITIONS_TRUNC,
        ),
    ],
    ids=["image_full", "spec_full", "image_trunc", "spec_trunc"],
)
def rampfit_result(request, rtdata_module, resource_tracker):
    """Run RampFitStep

    Parameters
    ----------
    rtdata_module : pytest.fixture
        artifactory fixture for data retrieval

    Returns
    -------
    model, path : `ImageModel`, `pathlib.Path`
        Model and path to model.
    """
    # Setup inputs
    requirement, artifactory_path, conditions = request.param
    input_data = rtdata_module.get_data(str(artifactory_path))
    rtdata_module.input = input_data

    # Execute the step
    with resource_tracker.track():
        result_model = RampFitStep.call(input_data, save_results=True)

    # Setup outputs
    input_data_path = Path(input_data)
    output = replace_suffix(input_data_path.stem, "rampfit") + ".asdf"
    expected_path = input_data_path.parent / output

    # Get truths
    rtdata_module.output = output
    output_artifactory_path = Path("truth") / artifactory_path.parent / output
    rtdata_module.get_truth(str(output_artifactory_path))

    try:
        yield requirement, result_model, expected_path, conditions
    finally:
        result_model.close()


# #####
# Tests
# #####
@pytest.mark.bigdata
def test_log_tracked_resources(log_tracked_resources, rampfit_result):
    log_tracked_resources()


@pytest.mark.bigdata
def test_rampfit_step(rampfit_result, rtdata_module, ignore_asdf_paths, dms_logger):
    """Test rampfit result against various conditions"""
    requirement, model, expected_path, conditions = rampfit_result
    error_msgs = []
    for condition in conditions:
        try:
            condition(requirement, model, expected_path, dms_logger)
        except AssertionError as e:
            error_msgs.append(str(e))

    # Always do a full regression check.
    try:
        cond_science_verification(
            requirement,
            model,
            expected_path,
            rtdata_module,
            ignore_asdf_paths,
            dms_logger,
        )
    except AssertionError as e:
        error_msgs.append(str(e))

    def test_success():
        assert not len(error_msgs), "\n".join(error_msgs)

    test_success()
