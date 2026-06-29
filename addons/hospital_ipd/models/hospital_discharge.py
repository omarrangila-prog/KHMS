# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class HospitalDischarge(models.Model):
    """Discharge summary, one per admission (Phase 5 §5.5, Phase 3 §4).

    BLOCKING RULE (Phase 3 §4, Phase 5 §5.5): confirming a discharge is
    blocked -- at the model level, not just a UI warning -- while any
    branch the admission's visit opened (lab/radiology/prescription) is
    still pending. Per the dependency-boundary constraint documented on
    ``hospital.visit`` (this module deliberately does NOT depend on
    ``hospital_lab``/``hospital_radiology``/``hospital_pharmacy``), the
    check is generic: it calls
    ``visit_id._compute_pending_branches()``, the exact extension contract
    ``hospital_doctor`` built so any module owning a discharge-style gate
    can ask "what's still open for this visit" without importing the
    branch-owning models directly. Whichever of lab/radiology/pharmacy
    happen to be installed will have already taught that method about
    their own branch; if none are installed, only the prescription
    branch (owned by ``hospital_doctor`` itself) is checked -- correct
    behavior, not a gap.
    """

    _name = "hospital.discharge"
    _inherit = ["hospital.audit.mixin", "mail.thread", "mail.activity.mixin"]
    _description = "Hospital Discharge"
    _order = "discharge_datetime desc"

    admission_id = fields.Many2one(
        comodel_name="hospital.ipd.admission",
        string="Admission",
        required=True,
        ondelete="restrict",
        index=True,
        tracking=True,
    )
    visit_id = fields.Many2one(
        comodel_name="hospital.visit",
        string="Visit",
        related="admission_id.visit_id",
        store=True,
        index=True,
    )
    patient_id = fields.Many2one(
        comodel_name="hospital.patient",
        string="Patient",
        related="admission_id.patient_id",
        store=True,
        index=True,
    )
    discharge_type = fields.Selection(
        selection=[
            ("normal", "Normal"),
            ("ama", "Against Medical Advice"),
            ("deceased", "Deceased"),
            ("referred", "Referred"),
        ],
        string="Discharge Type",
        required=True,
        default="normal",
        tracking=True,
    )
    discharge_summary = fields.Text(string="Discharge Summary")
    follow_up_instructions = fields.Text(
        string="Follow-up Instructions",
        help="Skipped on the printed summary for deceased discharges "
             "(Phase 3 §7 'Death in care' exception).",
    )
    discharge_medication_ids = fields.One2many(
        comodel_name="hospital.discharge.medication",
        inverse_name="discharge_id",
        string="Discharge Medications",
    )
    discharged_by = fields.Many2one(
        comodel_name="res.users",
        string="Discharged By",
        default=lambda self: self.env.user,
        ondelete="set null",
    )
    discharge_datetime = fields.Datetime(string="Discharge Date/Time")
    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("confirmed", "Confirmed"),
        ],
        string="Status",
        required=True,
        default="draft",
        index=True,
        tracking=True,
    )
    blocking_items_summary = fields.Text(
        string="Blocking Items",
        compute="_compute_blocking_items_summary",
        help="Human-readable list of branches still pending on the "
             "visit, shown on the Discharge form's blocking-items panel "
             "(Phase 8 §16). Empty when discharge can be confirmed.",
    )
    ward_charge_amount = fields.Monetary(
        string="Ward Charge (LOS x daily rate)",
        compute="_compute_ward_charge_amount",
        currency_field="currency_id",
    )
    currency_id = fields.Many2one(
        comodel_name="res.currency",
        string="Currency",
        related="admission_id.company_id.currency_id",
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        related="admission_id.company_id",
        store=True,
        index=True,
    )

    _sql_constraints = [
        (
            "hospital_discharge_admission_uniq",
            "unique(admission_id)",
            "An admission can only have one discharge record.",
        ),
    ]

    @api.depends("admission_id.visit_id")
    def _compute_blocking_items_summary(self):
        for discharge in self:
            visit = discharge.admission_id.visit_id
            if not visit:
                discharge.blocking_items_summary = False
                continue
            pending = visit._compute_pending_branches().get(visit.id, [])
            discharge.blocking_items_summary = (
                ", ".join(sorted(set(pending))) if pending else False
            )

    @api.depends(
        "admission_id.length_of_stay_days",
        "admission_id.ward_id.daily_rate",
    )
    def _compute_ward_charge_amount(self):
        for discharge in self:
            admission = discharge.admission_id
            rate = admission.ward_id.daily_rate or 0.0
            los = admission.length_of_stay_days or 0.0
            discharge.ward_charge_amount = rate * los

    @api.constrains("state")
    def _check_no_pending_branches_on_confirm(self):
        """DB-level backstop (Phase 11 §6) for the same invariant
        ``action_confirm()`` already validates explicitly -- catches the
        edge case of a 'confirmed' discharge later being reverted to
        'draft' then re-confirmed via a direct write(), bypassing the
        action method.
        """
        for discharge in self:
            if discharge.state != "confirmed":
                continue
            visit = discharge.admission_id.visit_id
            pending = visit._compute_pending_branches().get(visit.id, []) if visit else []
            if pending:
                raise ValidationError(
                    _("Cannot confirm discharge: the following branches "
                      "are still pending for this visit: %s")
                    % ", ".join(sorted(set(pending)))
                )

    def action_confirm(self):
        """Confirm the discharge: validate no pending branches, finalize
        billing, free the bed, and close the visit (Phase 3 §4).

        Discharge sub-types (AMA/deceased/referred) all go through this
        same path -- they only change what is printed on the summary
        (Phase 3 §4/§7), never the bed-release/billing flow itself.
        """
        for discharge in self:
            if discharge.state == "confirmed":
                raise UserError(_("This discharge is already confirmed."))
            admission = discharge.admission_id
            if admission.state != "admitted":
                raise UserError(
                    _("Only an admitted patient's stay can be discharged."))
            visit = admission.visit_id
            pending = visit._compute_pending_branches().get(visit.id, []) if visit else []
            if pending:
                raise UserError(
                    _("Cannot confirm discharge: the following branches "
                      "are still pending for this visit: %s")
                    % ", ".join(sorted(set(pending)))
                )
            discharge.write({
                "state": "confirmed",
                "discharge_datetime": discharge.discharge_datetime or fields.Datetime.now(),
            })
            admission.write({"state": "discharged", "discharge_id": discharge.id})
            admission._release_bed()
            discharge._create_ward_billing_line()
            if visit:
                visit.action_to_billing()
                visit.action_done()
        return True

    def _create_ward_billing_line(self):
        """Extension point for the LOS ward-charge billing line.

        DELIBERATELY A NO-OP TODAY, following the exact same documented
        pattern as ``hospital_pharmacy``'s
        ``hospital.prescription.line._create_billing_line()``: Phase 5
        §6 says every billable event writes an ``account.move.line`` onto
        a draft ``account.move`` keyed by the admission, but no module in
        the build order so far owns that ``account.move`` integration
        (billing ownership is not yet assigned to a specific module in
        Phase 6). ``ward_charge_amount`` is already computed correctly
        (LOS x ward daily_rate) and available on this record for
        whichever future module (most likely ``hospital_reports`` or a
        dedicated billing module) adds real ``account.move`` creation --
        it should override this method via ``_inherit`` and call
        ``super()`` first.
        """
        return True
