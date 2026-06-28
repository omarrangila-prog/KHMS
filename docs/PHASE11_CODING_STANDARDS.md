# Phase 11 — Coding Standards

Binding for all twelve modules. Deviations require a documented reason in the PR description, not silent inconsistency.

---

## 1. Python

- **Style:** PEP8 + Odoo's own guidelines (OCA-style). Formatter: `black` (line length 88) + `isort` for imports. Linter: `flake8` with Odoo-aware plugins (`pylint-odoo`) in CI.
- **Model method order convention** (Odoo standard, enforced): private attributes → field declarations → `@api.depends`/compute methods → `@api.constrains` → `@api.onchange` → CRUD overrides (`create`/`write`/`unlink`) → action/business methods → private helper methods (`_`-prefixed).
- **Naming:**
  - Models: `hospital.snake.case` (dot-namespaced per Odoo convention).
  - Python classes: `PascalCase` matching the model (e.g., `class HospitalPatient(models.Model)`).
  - Fields: `snake_case`, Many2one FK fields suffixed `_id`, One2many/Many2many suffixed `_ids`.
  - Methods: `snake_case`; private/internal methods prefixed `_`.
  - Constants: `UPPER_SNAKE_CASE` at module level.
- **No raw SQL string interpolation** — ever. Parameterized `cr.execute(query, (params,))` only, per Phase 9 §11.
- **No bare `except:`** — always catch specific exceptions; user-facing errors raise `odoo.exceptions.UserError`/`ValidationError`, never leak stack traces to the UI.
- **Translations:** every user-facing string wrapped in `_()` (Odoo's translation function), per PRD NFR-6.
- **No business logic in views/controllers** — controllers and OWL components call model methods; model methods own the logic, so the same logic is reusable by a future API layer (Phase 4 §7) without duplication.
- **Docstrings:** only where the *why* isn't obvious from the method name/signature — consistent with the project's "comment the why, not the what" rule. No boilerplate docstrings on every method.

---

## 2. XML (Views, Data, Reports)

- **File organization:** one model's views per file (`views/hospital_patient_views.xml`), security in `security/`, data/demo in `data/`/`demo/`, reports in `report/`.
- **Record IDs:** `module_name.model_name_view_type` (e.g., `hospital_base.hospital_patient_view_form`) — fully qualified, no ID collisions across modules.
- **No inline styles** in XML — all styling via SCSS classes (Phase 7 design tokens), keeps the design system enforceable and themeable.
- **Inherited views** use `xpath`/`position` precisely targeted — never wholesale template replacement, which breaks on upstream Odoo changes and on other modules' inheritance chains.
- **QWeb reports:** extend the shared `hospital_reports` base layout (Phase 6 §11) rather than rebuilding header/footer per report.

---

## 3. OWL (JavaScript Components)

- **Structure:** one component per file, `ComponentName.js` + co-located `.xml` template + `.scss` if component-specific styling is needed.
- **State:** use OWL's `useState`/hooks idiomatically; no direct DOM manipulation outside OWL's reactivity unless wrapping a third-party widget.
- **Naming:** `PascalCase` for component classes/files, matching Odoo 19's own OWL component conventions.
- **No jQuery** — Odoo 19's frontend has fully moved to OWL; new code never reintroduces jQuery patterns.
- **Live updates** (queues, dashboards) use Odoo's bus service (`@web/core/bus_service`) consistently — one shared pattern across nurse/doctor/pharmacy/ward screens, not bespoke polling per screen.

---

## 4. JavaScript (general)

- ES2022+ syntax as supported by Odoo 19's build pipeline; no transpilation hacks beyond what Odoo's asset bundling already provides.
- Strict mode implicitly via ES modules; no global namespace pollution.

---

## 5. SCSS

- All new design tokens (Phase 7 §2 color palette, spacing scale) defined as SCSS variables in a single `hospital_base/static/src/scss/_variables.scss`, imported by every module's stylesheets — single source of truth, no redefinition per module.
- Component styles scoped under a `.o_hospital_*` class prefix to avoid leaking into or being affected by unrelated Odoo styles.
- Dark mode via the same variables responding to Odoo's existing dark-mode class toggle (Phase 7 §6) — no parallel dark-mode system.

---

## 6. PostgreSQL

- All schema changes happen through Odoo's ORM field declarations and `_sql_constraints` / `init()` hooks — never a hand-written migration script run outside Odoo's module update mechanism, which would desync from `ir.model`/`ir.model.fields` metadata.
- Indexes declared via `index=True` on fields, or via `init()` hook executing `CREATE INDEX IF NOT EXISTS` for advanced cases (trigram GIN indexes, partial unique indexes per Phase 5 §5.2) — idempotent, safe to re-run on module upgrade.
- Every non-trivial business invariant gets a DB-level constraint (`_sql_constraints` or `init()`-created `CHECK`/partial unique index) in addition to Python `@api.constrains` — Python validation alone is not trusted for data integrity (Phase 5 design principle).

---

## 7. Folder Structure (per module, standard Odoo layout)

```
hospital_<name>/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   └── hospital_<model>.py
├── views/
│   └── hospital_<model>_views.xml
├── wizards/
│   ├── __init__.py
│   └── hospital_<wizard>.py
├── controllers/          (only if needed)
├── report/
│   ├── hospital_<report>.xml
│   └── hospital_<report>_templates.xml
├── security/
│   ├── ir.model.access.csv
│   └── hospital_<name>_security.xml
├── data/
├── demo/
├── static/
│   ├── src/
│   │   ├── js/  (OWL components)
│   │   ├── xml/ (OWL templates)
│   │   └── scss/
│   └── description/
│       ├── icon.png
│       └── index.html
├── tests/
│   ├── __init__.py
│   └── test_<feature>.py
└── README.md
```

---

## 8. Git Strategy & Branching

- **Model:** trunk-based with short-lived feature branches — `main` always installable.
- **Branch naming:** `feature/<module>-<short-description>`, `fix/<module>-<short-description>`, e.g. `feature/hospital-ipd-bed-transfer`.
- **PRs:** one module/feature per PR where possible; PRs touching multiple modules only for genuinely cross-cutting changes (e.g., a shared mixin change).
- **Review:** every PR requires at least one review before merge; security-sensitive PRs (auth, ACL, record rules) require sign-off referencing the Phase 9 checklist.

---

## 9. Commit Message Convention

Conventional Commits style:

```
<type>(<module>): <short summary>

[optional body — why, not what]
```

Types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `perf`, `security`.

Example: `feat(hospital_ipd): enforce one-active-admission-per-bed via partial unique index`

---

## 10. Testing Strategy

- **Unit tests** (`odoo.tests.TransactionCase`): every model method with business logic (state transitions, computed fields, constraints).
- **Integration tests**: cross-module flows per Phase 3 workflows (e.g., full reception→nurse→doctor→pharmacy path as one test).
- **Constraint/concurrency tests**: DB-level constraints (Phase 5 §5.2 bed uniqueness) tested under simulated concurrent writes, not just sequential calls.
- **Performance tests**: dashboard/search query benchmarks against a seeded 1M-row dataset, run in CI on a schedule (not every PR, to keep CI fast) per Phase 10 Sprint 9/11.
- **Coverage expectation:** business-critical paths (Phase 3 workflows, Phase 5 constraints) at or near 100%; pure UI/view XML not subject to a numeric coverage target.

---

## 11. Documentation Requirements (per module)

- `README.md`: purpose, dependencies, key models, how to install/configure, screenshots of core screens.
- `static/description/index.html`: Odoo Apps Store-style marketing description (used if/when published).
- Inline code comments only where non-obvious (project-wide rule, Phase 11 §1).
- This `docs/` folder (Phases 1–12) remains the canonical cross-module architecture reference, updated if a later implementation decision diverges from the plan.

---

## Status

Coding standards complete. Proceeding to Phase 12 — Implementation Order.
