# -*- coding: utf-8 -*-
from odoo import api, fields, models


class HospitalDoctor(models.Model):
    """Doctor master data.

    Design note: ``hr.employee`` linkage (mentioned as optional in Phase 5
    §2.2) is intentionally NOT implemented in this module to avoid adding a
    hard dependency on the ``hr`` app to ``hospital_base`` -- every other
    addon in the suite depends on this module, so a heavyweight transitive
    dependency here would force ``hr`` onto installs that don't need it
    (e.g. small clinics). If a later module needs the HR linkage, it should
    add an optional ``employee_id`` field via ``_inherit`` in a module that
    already depends on ``hr``.
    """

    _name = "hospital.doctor"
    _description = "Hospital Doctor"
    _order = "name"

    user_id = fields.Many2one(
        comodel_name="res.users",
        string="User",
        required=True,
        ondelete="restrict",
        index=True,
        help="Login identity of the doctor.",
    )
    name = fields.Char(
        string="Name",
        related="user_id.name",
        store=True,
        readonly=True,
        index=True,
    )
    department_id = fields.Many2one(
        comodel_name="hospital.department",
        string="Department",
        ondelete="restrict",
        index=True,
    )
    specialization = fields.Char(string="Specialization")
    license_number = fields.Char(string="License Number")
    schedule_ids = fields.One2many(
        comodel_name="hospital.doctor.schedule",
        inverse_name="doctor_id",
        string="Weekly Schedule",
    )
    active = fields.Boolean(string="Active", default=True)
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        default=lambda self: self.env.company,
        index=True,
    )

    _sql_constraints = [
        (
            "hospital_doctor_user_uniq",
            "unique(user_id)",
            "This user is already linked to another doctor record.",
        ),
    ]

    @api.depends("name", "specialization")
    def _compute_display_name(self):
        for doctor in self:
            label = doctor.name or ""
            if doctor.specialization:
                label = "%s (%s)" % (label, doctor.specialization)
            doctor.display_name = label
