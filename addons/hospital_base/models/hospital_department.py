# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class HospitalDepartment(models.Model):
    _name = "hospital.department"
    _description = "Hospital Department"
    _order = "name"

    name = fields.Char(string="Department Name", required=True, index=True)
    code = fields.Char(string="Code", required=True, index=True)
    active = fields.Boolean(string="Active", default=True)
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        default=lambda self: self.env.company,
        index=True,
    )
    doctor_ids = fields.One2many(
        comodel_name="hospital.doctor",
        inverse_name="department_id",
        string="Doctors",
    )

    _sql_constraints = [
        (
            "hospital_department_code_company_uniq",
            "unique(code, company_id)",
            "A department with this code already exists for this company.",
        ),
    ]

    @api.depends("name", "code")
    def _compute_display_name(self):
        for department in self:
            if department.code:
                department.display_name = "%s [%s]" % (department.name, department.code)
            else:
                department.display_name = department.name

    @api.constrains("code")
    def _check_code(self):
        for department in self:
            if department.code and not department.code.strip():
                raise ValidationError(
                    _("Department code cannot be blank.")
                )
