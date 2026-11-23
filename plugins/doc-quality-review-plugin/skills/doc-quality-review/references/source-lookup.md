# Where UI text lives in the Odoo source

Use this when a label, menu path, default, or behavior needs confirming by hand, beyond what
`verify_ui_refs.py` found. All paths are relative to the module folder:
`odoo-src/addons/<module>/` (Community) or `enterprise/<module>/` (Enterprise).

## Find the modules for a page

1. Start from the doc path: `hr/attendances.rst` → modules named `hr_attendance*`.
2. Confirm with the manifests: `git -C <repo> grep -l "'name': '<App name>'" -- '*/__manifest__.py'`.
3. Add the Enterprise modules that extend it (`enterprise/<module>_*`), and the localization or
   bridge modules the page mentions (`hr_attendance_gantt`, `hr_work_entry_*`, and so on).
4. Pass them to the scripts as patterns: `--modules 'hr_attendance*'`.

## Lookup table

| What the docs show | Where it comes from | Notes |
|---|---|---|
| Field label | `fields.X(string="...")` in `models/*.py` | No `string`: Odoo uses the field name without `_id`/`_ids`, with `_` → space, in Title Case (`scheduled_date` → *Scheduled Date*). Related fields take the label of the field they point to. |
| Label overridden on one form | `<field name="x" string="..."/>` in `views/*.xml` | Applies to that view only. Another view can show the Python label. |
| Label changed by another module | `<xpath ...>` or `<field ... position="attributes">` with `<attribute name="string">` | Often in Enterprise. Search both repos for the field name with `position=`. |
| Settings | `<setting string="..." help="...">` in `views/res_config_settings_views.xml` | `<setting>` with no `string` takes the label of its inner `<field>`. `help` is the gray text under the setting. |
| Settings section titles | `<block title="...">` | US scope: italics, not `:guilabel:`. |
| A setting that installs a module | `module_<name> = fields.Boolean(...)` in `models/res_config_settings.py` | Confirms claims like "enabling this installs the X module". |
| Menus | `<menuitem name="..." parent="..." action="...">` in `views/*menu*.xml` or other view files | No `name`: the menu shows the action's `name`. Nested `<menuitem>` elements take the outer one as parent. |
| Window and dialog titles | The action's `<field name="name">`, or `title` in JS dialogs | |
| Buttons | `<button string="..."/>` in views; `_t("...")` in `static/src/**/*.js` | |
| Kiosk, Discuss, POS, and other client screens | OWL templates in `static/src/**/*.xml`, strings in `_t("...")` | Text is usually element content, not an attribute. |
| Selection options | `selection=[('key', 'Label'), ...]` on the field | The list order is the order in the drop-down menu. |
| Tooltips | `help="..."` on the field (Python or view) | |
| Default values | `default=...` on the field, `default_get`, or `data/*.xml` records | Check that the docs state the real default. |
| Access groups | `res.groups` records in `security/*.xml` (`name` field) | The group's displayed name, for example *Officer: Manage all attendances*. |
| Record rules | `ir.rule` records in `security/*.xml` | Confirms "users can only see their own..." claims. |
| Automated behavior | `@api.depends`, `@api.onchange`, `_cron_*` methods, `ir.cron` records | Confirms "Odoo automatically..." claims. |

## Pitfalls

- **XML escaping.** In XML, `&` is `&amp;` and `"` is `&quot;`. Decode before comparing.
  "Device & Location Tracking" is written `Device &amp; Location Tracking`.
- **Exact capitalization.** The docs must match the UI capitalization, even when the UI has a
  typo. A case-only difference is an accuracy finding, not a style one.
- **Trailing punctuation.** The docs drop ellipses and end punctuation from UI strings
  (`Add a line`, not `Add a line...`). Do not report that difference.
- **Translation files.** `i18n/*.pot` can lag the code. Use them only as a hint, never as proof.
- **Tests and demo data.** Strings in `tests/` or `demo/` are not UI. Rank them last.
- **Version.** The source checkouts must be on the same branch as the docs. Otherwise every
  difference is suspect.
- **Conditional UI.** `invisible=`, `groups=`, and `column_invisible=` attributes hide elements for
  some users or states. If the docs show an element that has one of these, check that the page
  states the condition (the app installed, the setting enabled, the access right).
