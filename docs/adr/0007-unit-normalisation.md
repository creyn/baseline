# 7. Unit normalisation: keep the original, derive a normalised value

Date: 2026-11-18

## Status

Accepted

## Context

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

### Considered options

1. **No normalisation.** Values are stored as printed, and each unit is a separate series on the chart. There is no risk of a wrong conversion, but the trend breaks whenever the laboratory changes.
2. **A conversion table in code, per parameter (LOINC code), covered by tests.** Deterministic, auditable and reviewable. It has to be maintained, and it covers only the parameters listed in it.
3. **A UCUM library.** UCUM is the standard unit notation used by FHIR. A library recognises equivalent notations (kind 1) and converts dimensions, e.g. mg to g. It cannot do kind 2 without the molar mass of each parameter.
4. **Let the model convert during extraction.** No code to write, but it breaks the rule that numbers do not come from a model without verification.

## Decision

We combine options 1, 2 and 3.

1. **The original is always stored**: value, unit and reference range exactly as printed. It is the source of truth.
2. **A normalised value is derived and stored next to it.** It can be recomputed whenever the conversion table changes.
3. **Kind 1 is handled by UCUM, kind 2 by a small table per LOINC code.** The table starts with the parameters found in the user's own results and grows when new ones appear. Every factor and formula has a test with known values.
4. **The reference range is converted with the same factor** as the value.
5. **No conversion, no guessing.** If no conversion is known, the chart shows two series with a note that the units differ.
6. **A change of method or analyser is marked on the chart**, with a note that the values may not be comparable. This is the answer to kind 3. The method and analyser are kept by masking ([ADR-0006](0006-zone-based-masking.md)).
7. **Normalisation lives in the .NET domain** and runs when a result is approved. Trends and the agent's tools are in .NET; Python only extracts ([ADR-0002](0002-split-between-dotnet-and-python.md)).
8. **The chart uses the unit of the most recent result by default**, i.e. the unit the doctor sees on the current report. The user can switch the unit per parameter.

## Consequences

- Trends survive a change of laboratory for every parameter in the table.
- The original value is never lost, so a wrong factor can be fixed and every value recomputed.
- The conversion table becomes part of the system and needs a test for every entry.
- Parameters outside the table still work, with a broken trend instead of a wrong one.
- Normalisation depends on LOINC mapping. A parameter without a LOINC code is not converted.
- The chart can say that two values are not comparable, which a single global unit would hide.
