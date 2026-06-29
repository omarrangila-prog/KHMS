# -*- coding: utf-8 -*-
from odoo import api, models


class HospitalPrescription(models.Model):
    """Pharmacy-side extension of the prescription header.

    ``_recompute_state_from_lines()`` already exists on the base model
    (``hospital_doctor.hospital.prescription``): it reads all non-cancelled
    line states and maps the aggregate to the prescription's own state.
    This module does not override that method -- it is already correct and
    called explicitly by :meth:`hospital.prescription.line.dispense` after
    each line transition (see ``hospital_pharmacy/models/
    hospital_prescription_line.py``).

    VISIT-LEVEL ROUTING: after ``_recompute_state_from_lines()`` the
    dispense method calls
    ``self.visit_id.action_route_from_consultation()`` on the visit
    directly. This invokes the existing routing machinery (from
    ``hospital_doctor``'s ``hospital.visit`` extension) without requiring
    any extension here: ``_compute_pending_branches()`` already checks
    ``hospital.prescription.state`` against ``['draft',
    'partially_dispensed']`` -- driving the state to ``'dispensed'``
    removes the prescription from that list, and if all other pending
    branches are also resolved, ``action_route_from_consultation()``
    advances the visit to ``billing`` automatically. Per
    ``hospital_doctor``'s README and ``_compute_pending_branches()``
    docstring, ``hospital_pharmacy`` is explicitly documented as NOT
    needing to extend that method.
    """

    _inherit = "hospital.prescription"

    @api.model
    def _demo_dispense_prescription(self, prescription_id, dispense_kwargs):
        """Demo-data helper: dispenses all lines on a prescription.

        Called by ``<function>`` tags in ``demo/hospital_pharmacy_demo.xml``
        with a prescription id and a dict of dispense kwargs (``qty``,
        ``override_allergy``, ``override_reason``). Using a single-dict arg
        rather than three positional ``<value>`` tags makes the XML
        more readable.
        """
        prescription = self.browse(prescription_id)
        qty = dispense_kwargs.get("qty")
        override_allergy = dispense_kwargs.get("override_allergy", False)
        override_reason = dispense_kwargs.get("override_reason")
        for line in prescription.line_ids:
            line.dispense(
                qty=qty,
                override_allergy=override_allergy,
                override_reason=override_reason,
            )
