#! /usr/bin/env python
from __future__ import annotations

from typing import TYPE_CHECKING

import roman_datamodels as rdm

from romancal.photom import photom
from romancal.stpipe import RomanStep

if TYPE_CHECKING:
    from typing import ClassVar

__all__ = ["PhotomStep"]


class PhotomStep(RomanStep):
    """
    PhotomStep: Module for loading photometric conversion information from
        reference files and attaching to the input science data model
    """

    class_alias = "photom"

    reference_file_types: ClassVar = ["photom"]

    def process(self, input):
        """Perform the photometric calibration step

        Parameters
        ----------
        input : Roman level 2 image datamodel (wfi_image-1.x.x)
            input roman datamodel

        Returns
        -------
        output_model : Roman level 2 image datamodel (wfi_image-1.x.x)
            output roman datamodel
        """

        if isinstance(input, rdm.DataModel):
            input_model = input
        else:
            input_model = rdm.open(input)

        # Get reference file
        reffile = self.get_reference_file(input_model, "photom")

        # Open the relevant photom reference file as a datamodel
        if reffile is not None and reffile != "N/A":
            # If there is a reference file, perform photom application
            photom_model = rdm.open(reffile)
            self.log.debug(f"Using PHOTOM ref file: {reffile}")

            # Do the correction
            if input_model.meta.exposure.type == "WFI_IMAGE":
                output_model = photom.apply_photom(input_model, photom_model)
                output_model.meta.cal_step.photom = "COMPLETE"
            else:
                self.log.warning("No photometric corrections for spectral data")
                self.log.warning("Photom step will be skipped")
                input_model.meta.cal_step.photom = "SKIPPED"
                input_model.meta.photometry.pixel_area = None
                input_model.meta.photometry.conversion_megajanskys = None
                input_model.meta.photometry.conversion_megajanskys_uncertainty = None
                output_model = input_model
            photom_model.close()

        else:
            # Skip Photom step if no photom file
            self.log.warning("No PHOTOM reference file found")
            self.log.warning("Photom step will be skipped")
            input_model.meta.cal_step.photom = "SKIPPED"
            output_model = input_model

        if self.save_results:
            try:
                self.suffix = "photom"
            except AttributeError:
                self["suffix"] = "photom"

        return output_model
