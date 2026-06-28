# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

# Clinically-informed sanity bounds (Phase 5 §3.1) -- these reject obvious
# data-entry errors, not clinical judgement. Named constants kept in one
# place so both the @api.constrains range checks and the abnormal-vitals
# escalation logic below read from the same source of truth (Phase 6 §3
# "Data files" note: no separate reference-data file, to avoid duplicating
# thresholds in two places).
BP_SYSTOLIC_MIN = 40
BP_SYSTOLIC_MAX = 300
BP_DIASTOLIC_MIN = 20
BP_DIASTOLIC_MAX = 200
PULSE_RATE_MIN = 1
PULSE_RATE_MAX = 300
TEMPERATURE_MIN = 30.0
TEMPERATURE_MAX = 45.0
SPO2_MIN = 0
SPO2_MAX = 100
RESPIRATORY_RATE_MIN = 1
RESPIRATORY_RATE_MAX = 100

# Abnormal-vitals escalation thresholds (Phase 3 §2): any one breach
# auto-flags the visit ``urgent`` (never de-escalating an existing
# ``emergency``) and auto-transitions waiting_nurse -> waiting_doctor.
ABNORMAL_BP_SYSTOLIC_HIGH = 180
ABNORMAL_BP_SYSTOLIC_LOW = 90
ABNORMAL_TEMPERATURE_HIGH = 39.0
ABNORMAL_TEMPERATURE_LOW = 35.0
ABNORMAL_SPO2_LOW = 92
ABNORMAL_PULSE_HIGH = 120
ABNORMAL_PULSE_LOW = 50

# BMI color-flag bands (Phase 8 §7 "BMI: 24.2 (Normal)") -- exposed via
# `bmi_status` so both the quick-entry OWL screen and any future report
# can reuse a single classification instead of re-deriving it from raw
# thresholds in JS.
BMI_UNDERWEIGHT_MAX = 18.5
BMI_NORMAL_MAX = 25.0
BMI_OVERWEIGHT_MAX = 30.0


class HospitalVitals(models.Model):
    _name = "hospital.vitals"
    _inherit = ["hospital.audit.mixin"]
    _description = "Hospital Vitals"
    _order = "create_date desc"

    visit_id = fields.Many2one(
        comodel_name="hospital.visit",
        string="Visit",
        required=True,
        ondelete="cascade",
        index=True,
    )
    recorded_by = fields.Many2one(
        comodel_name="res.users",
        string="Recorded By",
        default=lambda self: self.env.user,
    )
    blood_pressure_systolic = fields.Integer(string="BP Systolic (mmHg)")
    blood_pressure_diastolic = fields.Integer(string="BP Diastolic (mmHg)")
    pulse_rate = fields.Integer(string="Pulse Rate (bpm)")
    temperature = fields.Float(string="Temperature (°C)", digits=(4, 1))
    spo2 = fields.Integer(string="SpO2 (%)")
    respiratory_rate = fields.Integer(string="Respiratory Rate (breaths/min)")
    height_cm = fields.Float(string="Height (cm)", digits=(5, 1))
    weight_kg = fields.Float(string="Weight (kg)", digits=(5, 1))
    bmi = fields.Float(
        string="BMI",
        compute="_compute_bmi",
        store=True,
        digits=(5, 1),
    )
    bmi_status = fields.Selection(
        selection=[
            ("underweight", "Underweight"),
            ("normal", "Normal"),
            ("overweight", "Overweight"),
            ("obese", "Obese"),
        ],
        string="BMI Status",
        compute="_compute_bmi",
        store=True,
    )
    notes = fields.Text(string="Notes")
    is_abnormal = fields.Boolean(
        string="Abnormal",
        compute="_compute_is_abnormal",
        store=True,
        help="True if any recorded vital breaches the abnormal-vitals "
             "escalation thresholds (Phase 3 §2).",
    )
    patient_id = fields.Many2one(
        comodel_name="hospital.patient",
        string="Patient",
        related="visit_id.patient_id",
        store=True,
        index=True,
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        related="visit_id.company_id",
        store=True,
        index=True,
    )

    @api.depends("height_cm", "weight_kg")
    def _compute_bmi(self):
        for vitals in self:
            if vitals.height_cm and vitals.weight_kg:
                height_m = vitals.height_cm / 100.0
                vitals.bmi = vitals.weight_kg / (height_m ** 2)
            else:
                vitals.bmi = 0.0
            if not vitals.bmi:
                vitals.bmi_status = False
            elif vitals.bmi < BMI_UNDERWEIGHT_MAX:
                vitals.bmi_status = "underweight"
            elif vitals.bmi < BMI_NORMAL_MAX:
                vitals.bmi_status = "normal"
            elif vitals.bmi < BMI_OVERWEIGHT_MAX:
                vitals.bmi_status = "overweight"
            else:
                vitals.bmi_status = "obese"

    @api.depends(
        "blood_pressure_systolic",
        "temperature",
        "spo2",
        "pulse_rate",
    )
    def _compute_is_abnormal(self):
        for vitals in self:
            vitals.is_abnormal = vitals._get_abnormal_reasons() != []

    def _get_abnormal_reasons(self):
        """Return a list of human-readable reasons this record breaches
        the abnormal-vitals escalation thresholds (Phase 3 §2). An empty
        list means all recorded vitals are within the safe range.
        """
        self.ensure_one()
        reasons = []
        if self.blood_pressure_systolic and (
            self.blood_pressure_systolic > ABNORMAL_BP_SYSTOLIC_HIGH
            or self.blood_pressure_systolic < ABNORMAL_BP_SYSTOLIC_LOW
        ):
            reasons.append(_("blood pressure (systolic)"))
        if self.temperature and (
            self.temperature > ABNORMAL_TEMPERATURE_HIGH
            or self.temperature < ABNORMAL_TEMPERATURE_LOW
        ):
            reasons.append(_("temperature"))
        if self.spo2 and self.spo2 < ABNORMAL_SPO2_LOW:
            reasons.append(_("SpO2"))
        if self.pulse_rate and (
            self.pulse_rate > ABNORMAL_PULSE_HIGH
            or self.pulse_rate < ABNORMAL_PULSE_LOW
        ):
            reasons.append(_("pulse rate"))
        return reasons

    @api.constrains("spo2")
    def _check_spo2_range(self):
        for vitals in self:
            if vitals.spo2 and not (SPO2_MIN <= vitals.spo2 <= SPO2_MAX):
                raise ValidationError(
                    _("SpO2 must be between %(min)s and %(max)s%%.")
                    % {"min": SPO2_MIN, "max": SPO2_MAX}
                )

    @api.constrains("pulse_rate")
    def _check_pulse_rate_range(self):
        for vitals in self:
            if vitals.pulse_rate and not (
                PULSE_RATE_MIN <= vitals.pulse_rate <= PULSE_RATE_MAX
            ):
                raise ValidationError(
                    _("Pulse rate must be between %(min)s and %(max)s bpm.")
                    % {"min": PULSE_RATE_MIN, "max": PULSE_RATE_MAX}
                )

    @api.constrains("temperature")
    def _check_temperature_range(self):
        for vitals in self:
            if vitals.temperature and not (
                TEMPERATURE_MIN <= vitals.temperature <= TEMPERATURE_MAX
            ):
                raise ValidationError(
                    _("Temperature must be between %(min)s°C and %(max)s°C.")
                    % {"min": TEMPERATURE_MIN, "max": TEMPERATURE_MAX}
                )

    @api.constrains("respiratory_rate")
    def _check_respiratory_rate_range(self):
        for vitals in self:
            if vitals.respiratory_rate and not (
                RESPIRATORY_RATE_MIN <= vitals.respiratory_rate <= RESPIRATORY_RATE_MAX
            ):
                raise ValidationError(
                    _("Respiratory rate must be between %(min)s and "
                      "%(max)s breaths/min.")
                    % {"min": RESPIRATORY_RATE_MIN, "max": RESPIRATORY_RATE_MAX}
                )

    @api.constrains("blood_pressure_systolic", "blood_pressure_diastolic")
    def _check_blood_pressure_range(self):
        for vitals in self:
            if vitals.blood_pressure_systolic and not (
                BP_SYSTOLIC_MIN <= vitals.blood_pressure_systolic <= BP_SYSTOLIC_MAX
            ):
                raise ValidationError(
                    _("Systolic blood pressure must be between %(min)s "
                      "and %(max)s mmHg.")
                    % {"min": BP_SYSTOLIC_MIN, "max": BP_SYSTOLIC_MAX}
                )
            if vitals.blood_pressure_diastolic and not (
                BP_DIASTOLIC_MIN <= vitals.blood_pressure_diastolic <= BP_DIASTOLIC_MAX
            ):
                raise ValidationError(
                    _("Diastolic blood pressure must be between %(min)s "
                      "and %(max)s mmHg.")
                    % {"min": BP_DIASTOLIC_MIN, "max": BP_DIASTOLIC_MAX}
                )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._check_abnormal_and_escalate()
        return records

    def _check_abnormal_and_escalate(self):
        """Abnormal-vitals auto-escalation + auto-transition (Phase 3 §2,
        the key business rule of this module).

        Called from ``create()`` *after* ``super().create()`` so the
        computed ``bmi``/``is_abnormal`` fields are already set on
        ``self``. For every vitals record:

        1. If any vital breaches the abnormal thresholds, the related
           visit's ``priority`` is escalated to ``urgent`` -- but only
           ever escalates, never de-escalates an existing ``emergency``
           priority.
        2. The visit is then moved from ``waiting_nurse`` to
           ``waiting_doctor`` via ``action_vitals_recorded()`` (added to
           ``hospital.visit`` by this module's ``models/hospital_visit.py``
           _inherit), regardless of whether vitals were abnormal --
           recording vitals always sends the patient to the doctor queue.
        """
        for vitals in self:
            visit = vitals.visit_id
            if not visit:
                continue
            if vitals.is_abnormal and visit.priority != "emergency":
                visit.priority = "urgent"
            if visit.state == "waiting_nurse":
                visit.action_vitals_recorded()
