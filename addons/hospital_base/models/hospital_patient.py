# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class HospitalPatient(models.Model):
    _name = "hospital.patient"
    _inherit = ["hospital.audit.mixin", "mail.thread", "mail.activity.mixin"]
    _description = "Hospital Patient"
    _order = "name"

    patient_code = fields.Char(
        string="Patient Code",
        required=True,
        copy=False,
        readonly=True,
        index=True,
        default=lambda self: _("New"),
    )
    name = fields.Char(string="Full Name", required=True, index=True, tracking=True)
    date_of_birth = fields.Date(string="Date of Birth", required=True, tracking=True)
    age = fields.Integer(string="Age", compute="_compute_age", store=True)
    gender = fields.Selection(
        selection=[
            ("male", "Male"),
            ("female", "Female"),
            ("other", "Other"),
        ],
        string="Gender",
    )
    blood_group = fields.Selection(
        selection=[
            ("a_pos", "A+"),
            ("a_neg", "A-"),
            ("b_pos", "B+"),
            ("b_neg", "B-"),
            ("o_pos", "O+"),
            ("o_neg", "O-"),
            ("ab_pos", "AB+"),
            ("ab_neg", "AB-"),
            ("unknown", "Unknown"),
        ],
        string="Blood Group",
        default="unknown",
    )
    phone = fields.Char(string="Phone", required=True, index=True)
    mobile = fields.Char(string="Mobile", index=True)
    email = fields.Char(string="Email")
    address_id = fields.Many2one(
        comodel_name="res.partner",
        string="Billing Contact",
        ondelete="restrict",
        help="Optional link to a full Odoo partner for billing/portal reuse.",
    )
    identity_type = fields.Selection(
        selection=[
            ("national_id", "National ID"),
            ("passport", "Passport"),
            ("other", "Other"),
        ],
        string="Identity Type",
        default="national_id",
    )
    identity_number = fields.Char(string="Identity Number", index=True)
    emergency_contact_name = fields.Char(string="Emergency Contact Name")
    emergency_contact_phone = fields.Char(string="Emergency Contact Phone")
    allergy_ids = fields.One2many(
        comodel_name="hospital.patient.allergy",
        inverse_name="patient_id",
        string="Allergies",
    )
    chronic_condition_ids = fields.One2many(
        comodel_name="hospital.patient.condition",
        inverse_name="patient_id",
        string="Chronic Conditions",
    )
    visit_ids = fields.One2many(
        comodel_name="hospital.visit",
        inverse_name="patient_id",
        string="Visits",
    )
    visit_count = fields.Integer(string="Visit Count", compute="_compute_visit_count")
    active = fields.Boolean(string="Active", default=True)
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        default=lambda self: self.env.company,
        index=True,
    )

    _sql_constraints = [
        (
            "hospital_patient_code_uniq",
            "unique(patient_code)",
            "Patient code must be unique.",
        ),
    ]

    @api.depends("date_of_birth")
    def _compute_age(self):
        today = fields.Date.context_today(self)
        for patient in self:
            if patient.date_of_birth:
                patient.age = relativedelta(today, patient.date_of_birth).years
            else:
                patient.age = 0

    def _compute_visit_count(self):
        visit_data = self.env["hospital.visit"].read_group(
            domain=[("patient_id", "in", self.ids)],
            fields=["patient_id"],
            groupby=["patient_id"],
        )
        counts = {
            data["patient_id"][0]: data["patient_id_count"] for data in visit_data
        }
        for patient in self:
            patient.visit_count = counts.get(patient.id, 0)

    @api.depends("name", "patient_code")
    def _compute_display_name(self):
        for patient in self:
            if patient.patient_code:
                patient.display_name = "%s (%s)" % (patient.name, patient.patient_code)
            else:
                patient.display_name = patient.name

    @api.constrains("date_of_birth")
    def _check_date_of_birth(self):
        today = fields.Date.context_today(self)
        for patient in self:
            if patient.date_of_birth and patient.date_of_birth > today:
                raise ValidationError(
                    _("Date of birth cannot be in the future.")
                )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("patient_code") or vals.get("patient_code") == _("New"):
                vals["patient_code"] = self.env["ir.sequence"].next_by_code(
                    "hospital.patient"
                ) or _("New")
        return super().create(vals_list)

    @api.model
    def _name_search(self, name="", domain=None, operator="ilike", limit=None, order=None):
        domain = domain or []
        if name:
            domain = [
                "|",
                "|",
                ("name", operator, name),
                ("patient_code", operator, name),
                ("phone", operator, name),
            ] + domain
        return self._search(domain, limit=limit, order=order)

    def check_duplicate(self):
        """Reusable duplicate-detection service.

        Returns recordsets of potential duplicate patients matched by
        ``identity_number`` (excluding ``self``). This is a non-blocking,
        informational check by design (Phase 3 FR-3 / Phase 5 §1.1) -- the
        caller (e.g. the reception registration flow built in
        ``hospital_reception``) decides how to surface the warning; this
        method never raises and never blocks ``create``/``write``.
        """
        result = {}
        for patient in self:
            matches = self.browse()
            if patient.identity_number:
                matches = self.search(
                    [
                        ("identity_number", "=", patient.identity_number),
                        ("id", "!=", patient.id),
                    ]
                )
            result[patient.id] = matches
        return result

    def action_view_visits(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "hospital_base.hospital_visit_action"
        )
        action["domain"] = [("patient_id", "=", self.id)]
        action["context"] = {"default_patient_id": self.id}
        return action
