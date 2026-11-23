# 11. Lab parameters: dictionary, units and reference ranges

Date: 2026-11-23

## Status

Accepted. Carried over from the earlier set of decisions (2026-11-18). Changed on 2026-11-23: aliases are shared by all users, the model's suggestion comes from extraction, and normalised values are recomputed when the conversion table changes.

## Context

How a parameter printed by a laboratory becomes a point on a trend: the dictionary that names it, the conversion of its unit, and its reference range. The three depend on each other and are read together.

### Unit normalisation: keep the original, derive a normalised value

The same parameter arrives in different units, depending on the laboratory and the year. A trend chart that ignores this either breaks or, worse, shows a jump that did not happen.

There are three kinds of difference:

1. **The same unit, written differently.** µIU/ml is mIU/l. tys/µl is 10^3/µl and 10^9/l. Only the notation differs.
2. **A different unit with a parameter-specific factor.** Examples:
   - vitamin D: ng/ml × 2.496 = nmol/l,
   - glucose: mg/dl ÷ 18.0 = mmol/l,
   - creatinine: mg/dl × 88.4 = µmol/l.

   The factor comes from the molar mass, so it depends on the parameter. Some conversions are formulas, not factors: HbA1c in % (NGSP) to mmol/mol (IFCC) is (% − 2.15) × 10.929.
3. **The same unit, but values that are not comparable.** A different method or analyser can give different values for the same sample, e.g. vitamin D or TSH assays. No conversion fixes this.

The project has a rule that numbers do not come from a model without verification.

#### Considered options

1. **No normalisation.** Values are stored as printed, and each unit is a separate series on the chart. There is no risk of a wrong conversion, but the trend breaks whenever the laboratory changes.
2. **A conversion table in code, per parameter (LOINC code), covered by tests.** Deterministic, auditable and reviewable. It has to be maintained, and it covers only the parameters listed in it.
3. **A UCUM library.** UCUM is the standard unit notation used by FHIR. A library recognises equivalent notations (kind 1) and converts dimensions, e.g. mg to g. It cannot do kind 2 without the molar mass of each parameter.
4. **Let the model convert during extraction.** No code to write, but it breaks the rule that numbers do not come from a model without verification.

### Reference ranges are stored with each result

A reference range is not one number per parameter.

1. **Every laboratory has its own ranges.** They depend on the method and the analyser. For TSH, for example, one laboratory prints 0.27–4.20 and another 0.40–4.00.
2. **Ranges change over time**, with a new reagent or analyser, and with the patient's age. Lab reports say so explicitly, e.g. "age-specific reference ranges were applied".
3. **Ranges come in many forms:**
   - an interval ("0.27–4.20"),
   - one-sided ("<190", ">30"),
   - descriptive ("negative"),
   - several ranges at once (hormones by cycle phase, age bands),
   - missing.
4. **A flag (H, L) is printed on most reports, but not all.** A flag computed by us could disagree with the printed one.

#### Considered options

1. **One global range per parameter**, from a table in code. Simple, but wrong: a result within the range of its laboratory may look out of range against our table, while the doctor reads the range on the report.
2. **The range stored with each result, as printed.** Always matches what the doctor saw. Changes over time and between laboratories show up by themselves. The range moves on the chart, which has to be shown clearly.
3. **A table of ranges per laboratory and period**, built from the documents. Stores fewer duplicates, but needs the laboratory and the validity dates to be recognised, and gains nothing over option 2.
4. **Option 2 plus a personal target set by the user**, e.g. a vitamin D target of 30–50 recommended by their doctor, or LDL below 70. A separate line on the chart, not a laboratory range.

### Parameter dictionary: definitions in the repository, lab names in the database

Laboratories name the same parameter differently: "TSH", "Tyreotropina (TSH) III generacji", "Hormon tyreotropowy". A trend is continuous, and the unit conversions (above) apply, only if all of them map to the same parameter. Every new laboratory brings new names.

Since [ADR-0003](0003-masking-in-the-browser-and-a-second-check.md), the dictionary has nothing to do with masking. Changing it cannot reveal personal data.

Two findings shaped the model:
- **One parameter can have several LOINC codes.** LOINC separates the property measured, e.g. glucose in mg/dl (mass concentration) and in mmol/l (substance concentration) have different codes. Our parameter is a broader concept, so that conversions can join them.
- **The name is not enough.** Glucose in blood and in urine are different parameters. Glucose fasting, 1 hour and 2 hours after a 75 g load (oral glucose tolerance test) are different measurements with different reference ranges, and LOINC gives each its own code. Putting them in one series would show a false jump. The same applies to insulin in a tolerance test, morning and evening cortisol, and hormones by cycle phase.

#### Considered options

1. **Repository only.** Reviewed and tested, but every new laboratory name needs a code change and a deploy before its trend joins up.
2. **Database only, edited by the user.** Immediate, but there is no shared starting set and no tests.
3. **Definitions in the repository, laboratory names in the database.** Parameters, LOINC codes, units and conversions are in the repository, with tests. Aliases such as "Tyreotropina → TSH" are in the database and added by the user.
4. **Option 3 plus suggestions on the review screen.** For a new name the system proposes a parameter, and the user confirms with one click.

## Decision

### Unit normalisation: keep the original, derive a normalised value

We combine options 1, 2 and 3.

1. **The original is always stored**: value, unit and reference range exactly as printed. It is the source of truth.
2. **A normalised value is derived and stored next to it.** It can be recomputed whenever the conversion table changes.
3. **Kind 1 is handled by UCUM, kind 2 by a small table per LOINC code.** The table starts with the parameters found in the user's own results and grows when new ones appear. Every factor and formula has a test with known values.
4. **The reference range is converted with the same factor** as the value.
5. **No conversion, no guessing.** If no conversion is known, the chart shows two series with a note that the units differ.
6. **A change of method or analyser is marked on the chart**, with a note that the values may not be comparable. This is the answer to kind 3. The method and analyser are kept by masking ([ADR-0003](0003-masking-in-the-browser-and-a-second-check.md)).
7. **Normalisation lives in the .NET domain** and runs when a result is approved. Trends and the agent's tools are in .NET; Python only extracts ([ADR-0002](0002-languages-dotnet-python-and-typescript.md)).
8. **The conversion table has a version.** When the API starts with a newer table than the one stored in the database, it recomputes the normalised values and computed flags of approved results, then stores the new version. A failure leaves the old values and is retried at the next start.
9. **The chart uses the unit of the most recent result by default**, i.e. the unit the doctor sees on the current report. The user can switch the unit per parameter.

### Reference ranges are stored with each result

We choose option 2 now. Option 4 is in the backlog.

1. **Every result stores its range in two forms:**
   - as text, exactly as printed;
   - parsed: lower bound, upper bound, and kind (interval, "<", ">", descriptive).

   If the range cannot be parsed, e.g. several ranges at once, only the text is kept and no flag is computed from it.
2. **The laboratory's flag wins.**
   - We compute a flag only when the report has none, and mark it as computed.
   - If both exist and disagree, the review screen shows it, because it often means an extraction error.
3. **On the chart, the range is a band that can change at every point.** A change of ranges by the laboratory is visible. Each point is coloured against the range of its own result.
4. **The range is converted together with the value** (see the units above).
5. **The agent judges "in range" or "out of range" only against the range of the result itself**, never against the model's general knowledge. This becomes part of the agent guardrails.

### Parameter dictionary: definitions in the repository, lab names in the database

We choose option 4.

1. **The repository holds everything that is a number or a rule:**
   - parameters,
   - their LOINC codes (one or more per parameter),
   - the material,
   - the measurement conditions,
   - units and conversion factors.

   It changes rarely, and every entry has tests.
2. **The database holds naming.** An alias maps the name printed by a laboratory to a parameter and a condition. The alias key is **name + material + condition**.
   - **Aliases are shared by all users.** A laboratory's name for a parameter is not personal data, so a name confirmed by one family member is matched for everyone. The alias table has no user id, is not under Row-Level Security, and is not deleted with an account.
3. **A measurement condition is part of the result:**
   - fasting,
   - a time after a load (e.g. 1 h or 2 h after 75 g of glucose),
   - a time of day,
   - a cycle phase,
   - unspecified.

   **Every condition is a separate series**, with the reference ranges of its own results (see the ranges above). "Unspecified" is drawn on the same chart as "fasting" with a different marker. On review, the user can set the condition with one click.
4. **Tolerance tests get their own view.** The 0, 1 and 2 hour points of one day form a small curve, and curves from different days can be compared.
5. **Suggestions for a new name, in this order:**
   1. an exact alias from the database,
   2. the ICD-9 PL code printed on the result (e.g. L69 for TSH), stored with every result,
   3. a similar known name,
   4. the parameter suggested by the model during extraction ([ADR-0007](0007-extraction-with-document-intelligence-and-an-llm.md)); there is no separate model call.
6. **Nothing is mapped without the user's confirmation.** A model proposal is only a proposal. An alias is stored after "Confirm", so the next result from that laboratory is matched exactly.
7. **An unmapped parameter is not rejected.** It gets its own series under the printed name until the user maps it.

## Consequences

### Unit normalisation: keep the original, derive a normalised value

- Trends survive a change of laboratory for every parameter in the table.
- The original value is never lost, so a wrong factor can be fixed and every value recomputed.
- The conversion table becomes part of the system and needs a test for every entry.
- Parameters outside the table still work, with a broken trend instead of a wrong one.
- Normalisation depends on LOINC mapping. A parameter without a LOINC code is not converted.
- The chart can say that two values are not comparable, which a single global unit would hide.

### Reference ranges are stored with each result

- What the user sees always matches the report the doctor saw.
- There is no reference range table to maintain.
- Ranges that cannot be parsed are still shown as text, but they give no computed flag and no band on the chart.
- A disagreement between the printed and the computed flag doubles as a check on extraction.
- A personal target, if added later, is kept apart from laboratory ranges, so the two cannot be confused.

### Parameter dictionary: definitions in the repository, lab names in the database

- Trends join up across laboratories without a deploy, after one confirmation per new name.
- Conversions and units stay reviewed and tested in the repository.
- Fasting and post-load values are never mixed, and neither are blood and urine.
- Extraction must return the material and the measurement condition of every result, besides the value, unit, range, dates, method and analyser.
- The parameter list in the repository needs an entry, with its LOINC codes, for every parameter the user wants converted.
- A wrong confirmation by the user joins two series, for every user, because aliases are shared. It can be undone by editing the alias, because the original printed name is stored with every result.
