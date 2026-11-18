# 12. Parameter dictionary: definitions in the repository, lab names in the database

Date: 2026-11-18

## Status

Accepted

## Context

Laboratories name the same parameter differently: "TSH", "Tyreotropina (TSH) III generacji", "Hormon tyreotropowy". A trend is continuous, and the conversions from [ADR-0007](0007-unit-normalisation.md) apply, only if all of them map to the same parameter. Every new laboratory brings new names.

Since [ADR-0006](0006-zone-based-masking.md), the dictionary has nothing to do with masking. Changing it cannot reveal personal data.

Two findings shaped the model:
- **One parameter can have several LOINC codes.** LOINC separates the property measured, e.g. glucose in mg/dl (mass concentration) and in mmol/l (substance concentration) have different codes. Our parameter is a broader concept, so that conversions can join them.
- **The name is not enough.** Glucose in blood and in urine are different parameters. Glucose fasting, 1 hour and 2 hours after a 75 g load (oral glucose tolerance test) are different measurements with different reference ranges, and LOINC gives each its own code. Putting them in one series would show a false jump. The same applies to insulin in a tolerance test, morning and evening cortisol, and hormones by cycle phase.

### Considered options

1. **Repository only.** Reviewed and tested, but every new laboratory name needs a code change and a deploy before its trend joins up.
2. **Database only, edited by the user.** Immediate, but there is no shared starting set and no tests.
3. **Definitions in the repository, laboratory names in the database.** Parameters, LOINC codes, units and conversions are in the repository, with tests. Aliases such as "Tyreotropina → TSH" are in the database and added by the user.
4. **Option 3 plus suggestions on the review screen.** For a new name the system proposes a parameter, and the user confirms with one click.

## Decision

We choose option 4.

1. **The repository holds everything that is a number or a rule:**
   - parameters,
   - their LOINC codes (one or more per parameter),
   - the material,
   - the measurement conditions,
   - units and conversion factors.

   It changes rarely, and every entry has tests.
2. **The database holds naming.** An alias maps the name printed by a laboratory to a parameter and a condition. The alias key is **name + material + condition**.
3. **A measurement condition is part of the result:**
   - fasting,
   - a time after a load (e.g. 1 h or 2 h after 75 g of glucose),
   - a time of day,
   - a cycle phase,
   - unspecified.

   **Every condition is a separate series**, with the reference ranges of its own results ([ADR-0008](0008-reference-ranges.md)). "Unspecified" is drawn on the same chart as "fasting" with a different marker. On review, the user can set the condition with one click.
4. **Tolerance tests get their own view.** The 0, 1 and 2 hour points of one day form a small curve, and curves from different days can be compared.
5. **Suggestions for a new name, in this order:**
   1. an exact alias from the database,
   2. the ICD-9 PL code printed on the result (e.g. L69 for TSH), stored with every result,
   3. a similar known name,
   4. a proposal from the model.
6. **Nothing is mapped without the user's confirmation.** A model proposal is only a proposal. An alias is stored after "Confirm", so the next result from that laboratory is matched exactly.
7. **An unmapped parameter is not rejected.** It gets its own series under the printed name until the user maps it.

## Consequences

- Trends join up across laboratories without a deploy, after one confirmation per new name.
- Conversions and units stay reviewed and tested in the repository.
- Fasting and post-load values are never mixed, and neither are blood and urine.
- Extraction must return the material and the measurement condition of every result, besides the value, unit, range, dates, method and analyser.
- The parameter list in the repository needs an entry, with its LOINC codes, for every parameter the user wants converted.
- A wrong confirmation by the user joins two series. It can be undone by editing the alias, because the original printed name is stored with every result.
