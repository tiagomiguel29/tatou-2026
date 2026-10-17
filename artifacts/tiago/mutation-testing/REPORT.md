# Phase II: Mutation testing

Tiago Oliveira

I focused on PDF upload validation because accepting invalid files can expose
Tatou to attacks. I used mutmut 3.8.0 with Python 3.12 to introduce small faults
and check whether our tests detected them. Tests exercised the real upload route
using temporary files and an isolated SQLite database.

## Results

I started with four existing upload tests and expanded them to 18 cases.

| Stage | Tests | Mutations caught | Surviving |
|---|---:|---:|---:|
| Original code and existing tests | 4 | 30/35 | 5 |
| Original code and stronger tests | 11 | 31/35 | 4 |
| Corrected code and final tests | 18 | 46/55 | 9 |

The final stage uses different mutations because the code changed, so its score
cannot be directly compared with the earlier stages.

## Findings and changes

Original mutant 14 exposed a missing boundary test. Adding a PDF with exactly
1019 trailing spaces caught its one-byte offset error.

Investigating original mutant 23 revealed a real bug: valid PDFs with long trailing
whitespace were rejected. Cases with 1020, 2048 and 8192 spaces failed before the
fix. I changed validation to scan backward in small chunks; those cases now pass.

I added tests rejecting extra trailing characters, catching final-code mutants
28 and 32, and strengthened assertions for stored bytes, hashes, metadata and
cleanup after failures.

## Assessment

Nine mutations survived. Seven appear to preserve acceptance behavior for stable
files through equivalent offsets, chunk sizes or unreachable conditions. Mutants
30 and 31 preserve acceptance but can increase resource use. These are reasoned
assessments, not formal proofs; all nine remain in the score.

The recorded full suite passed 47 tests with six applicability skips. Validator
line coverage was 95.5%, versus 50% across the project. This focused experiment
does not establish the security of other routes or PDF contents.

The main README explains how to rerun the experiment and what each test checks.
The other files include the results, copies of the code and tests, and records
showing that the results were repeated.
