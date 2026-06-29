# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class HospitalIpdAdmission(models.Model):
    """Inpatient admission record (Phase 5 §5.3, Phase 3 §4).

    State machine::

        requested -> waiting_for_bed -> admitted -> discharged
                                     \\-> cancelled

    ``waiting_for_bed`` is reachable from ``requested`` when a ward
    manager attempts a bed assignment and finds no vacant bed (Phase 3
    §4 edge case: "No bed available at request time: admission is queued
    ... visible to ward managers across all wards"). A bed transfer
    mid-stay never creates a new admission -- it is a child
    ``hospital.bed.transfer`` row under this same record (see that
    model).

    CONCURRENCY DESIGN -- the one-active-admission-per-bed guarantee
    ====================================================================
    Phase 5 §5.2 requires, at the DATABASE level (not just Python), that
    at most one ``hospital.ipd.admission`` row with ``state = 'admitted'``
    exists per ``bed_id``. Python-level checks (e.g. "is this bed
    vacant?" read-then-write) are subject to a classic race: two ward
    managers assigning the same free bed at the same instant could both
    pass the Python check before either commits. The fix is a PostgreSQL
    **partial unique index**::

        CREATE UNIQUE INDEX ... ON hospital_ipd_admission (bed_id)
        WHERE state = 'admitted'

    created idempotently in ``init()`` below. The second concurrent
    transaction's ``INSERT``/``UPDATE`` raises a ``psycopg2.IntegrityError``
    at the database level, which Odoo's ORM surfaces as a
    ``psycopg2.errors.UniqueViolation`` -- ``action_assign_bed()`` lets
    this propagate (rather than swallowing it), so the losing request
    fails loudly and the caller can retry against a different bed,
    exactly per Phase 10 Sprint 8's "two simultaneous admission attempts
    ... only one succeeds, with a clean error for the other" DoD.
    """

    _name = "hospital.ipd.admission"
    _inherit = ["hospital.audit.mixin", "mail.thread", "mail.activity.mixin"]
    _description = "Hospital IPD Admission"
    _order = "admission_datetime desc"

    admission_code = fields.Char(
        string="Admission Code",
        required=True,
        copy=False,
        readonly=True,
        index=True,
        default=lambda self: _("New"),
    )
    patient_id = fields.Many2one(
        comodel_name="hospital.patient",
        string="Patient",
        required=True,
        ondelete="restrict",
        index=True,
        tracking=True,
    )
    visit_id = fields.Many2one(
        comodel_name="hospital.visit",
        string="Visit",
        required=True,
        ondelete="restrict",
        index=True,
        tracking=True,
    )
    bed_id = fields.Many2one(
        comodel_name="hospital.bed",
        string="Bed",
        ondelete="restrict",
        index=True,
        tracking=True,
    )
    ward_id = fields.Many2one(
        comodel_name="hospital.ward",
        string="Ward",
        related="bed_id.ward_id",
        store=True,
        index=True,
    )
    admitting_doctor_id = fields.Many2one(
        comodel_name="hospital.doctor",
        string="Admitting Doctor",
        ondelete="restrict",
        index=True,
        tracking=True,
    )
    state = fields.Selection(
        selection=[
            ("requested", "Requested"),
            ("waiting_for_bed", "Waiting for Bed"),
            ("admitted", "Admitted"),
            ("discharged", "Discharged"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        required=True,
        default="requested",
        index=True,
        tracking=True,
    )
    admission_datetime = fields.Datetime(string="Admission Date/Time")
    discharge_id = fields.Many2one(
        comodel_name="hospital.discharge",
        string="Discharge",
        ondelete="set null",
        copy=False,
    )
    transfer_ids = fields.One2many(
        comodel_name="hospital.bed.transfer",
        inverse_name="admission_id",
        string="Bed Transfers",
    )
    length_of_stay_days = fields.Float(
        string="Length of Stay (days)",
        compute="_compute_length_of_stay_days",
        store=True,
        help="Computed from admission_datetime to the discharge's "
             "discharge_datetime (or now, if still admitted), used as "
             "the LOS billing multiplier against the ward's daily_rate.",
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        related="visit_id.company_id",
        store=True,
        index=True,
    )

    @api.depends("admission_datetime", "discharge_id.discharge_datetime", "state")
    def _compute_length_of_stay_days(self):
        for admission in self:
            if not admission.admission_datetime:
                admission.length_of_stay_days = 0.0
                continue
            end = admission.discharge_id.discharge_datetime or fields.Datetime.now()
            delta = end - admission.admission_datetime
            admission.length_of_stay_days = max(delta.total_seconds() / 86400.0, 0.0)

    @api.constrains("bed_id", "state")
    def _check_bed_required_when_admitted(self):
        for admission in self:
            if admission.state == "admitted" and not admission.bed_id:
                raise ValidationError(
                    _("An admission cannot be in the 'Admitted' state "
                      "without an assigned bed.")
                )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("admission_code", _("New")) == _("New"):
                vals["admission_code"] = self.env["ir.sequence"].next_by_code(
                    "hospital.ipd.admission"
                ) or _("New")
        return super().create(vals_list)

    def init(self):
        """Idempotent DB-level partial unique index (Phase 5 §5.2,
        Phase 11 §6): at most one 'admitted' admission per bed.

        Uses a fixed, static DDL string with no interpolated user data
        (Phase 9 §11) -- ``CREATE UNIQUE INDEX IF NOT EXISTS`` is itself
        idempotent so this is also safe to re-run on every module
        upgrade, per Phase 11 §6.
        """
        self.env.cr.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS "
            "hospital_ipd_admission_one_active_per_bed "
            "ON hospital_ipd_admission (bed_id) "
            "WHERE state = 'admitted'"
        )

    def action_request(self):
        """Re-open a cancelled admission request (rarely used; mainly
        kept symmetrical with the other explicit action_* transitions).
        """
        for admission in self:
            if admission.state != "cancelled":
                raise UserError(_("Only a cancelled admission can be re-requested."))
            admission.state = "requested"
        return True

    def action_assign_bed(self, bed_id):
        """Assign a vacant bed and transition to ``admitted``.

        Raises ``UserError`` for ordinary business-rule violations (bed
        not vacant, wrong admission state). A genuine race against
        another concurrent assignment to the SAME bed is instead caught
        by the partial unique index at the database level (see class
        docstring) and surfaces as an ``IntegrityError`` -- intentionally
        NOT swallowed here, so the caller sees a clean failure rather
        than silent data corruption.
        """
        bed = self.env["hospital.bed"].browse(bed_id)
        for admission in self:
            if admission.state not in ("requested", "waiting_for_bed"):
                raise UserError(
                    _("Only admissions in 'Requested' or 'Waiting for Bed' "
                      "state can be assigned a bed.")
                )
            if bed.state != "vacant":
                raise UserError(
                    _("Bed %s is not vacant.") % bed.display_name
                )
            admission.write({
                "bed_id": bed.id,
                "state": "admitted",
                "admission_datetime": fields.Datetime.now(),
            })
            bed.write({
                "state": "occupied",
                "current_admission_id": admission.id,
            })
            admission.visit_id.action_admit()
        return True

    def action_mark_waiting_for_bed(self):
        """No vacant bed found at request time (Phase 3 §4 edge case)."""
        for admission in self:
            if admission.state != "requested":
                raise UserError(
                    _("Only a requested admission can be marked as "
                      "waiting for a bed."))
            admission.state = "waiting_for_bed"
        return True

    def action_cancel(self):
        for admission in self:
            if admission.state == "admitted":
                raise UserError(
                    _("An admitted patient cannot have their admission "
                      "cancelled directly -- discharge them instead."))
            if admission.state == "discharged":
                raise UserError(_("A discharged admission cannot be cancelled."))
            admission.state = "cancelled"
        return True

    def _release_bed(self):
        """Free the current bed (state -> cleaning) on discharge.

        Private helper called only from ``hospital.discharge.action_confirm()``
        -- never exposed as a standalone button, since releasing a bed
        outside the discharge flow would desync ``hospital.bed.state``
        from the admission state machine.
        """
        for admission in self:
            if admission.bed_id:
                admission.bed_id.write({
                    "state": "cleaning",
                    "current_admission_id": False,
                })
        return True
