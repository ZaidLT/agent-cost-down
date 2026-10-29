# Protocol v4 amendment, October 30, 2026

Approved by Zaid Lattouf through the explicit implementation request in this chat. This note and the implementation must be committed before the first v4 model call. The assignment records that commit; the held-out freeze also records its execution commit and hashes.

## Declared interventions

A. The validator accepts a redundant quantity on replacement only when it equals the original line quantity. It accepts a redundant SKU on quantity amendments or returns only when it equals the original line SKU. Actual conflicts remain rejected. Authorization, inventory, return eligibility and transaction checks remain enforced.

B. Runtime failures provide specific bounded codes and valid field pointers through FailureContext version 2. This changes information available to a second attempt. It never supplies private expected answers, values or task-specific hints. Both retry policies receive equivalent context.

C. Diagnostics distinguish missing tool calls from malformed JSON. This changes labels, not retry behavior or accepted syntax. Validator version 2 and protocol 4 distinguish this experiment from the original reports. Reports reject mixed versions and incompatible assignment hashes.

V4 measures these declared changes together. It cannot attribute gains to either A or B alone. The offline replay is counterfactual diagnostic evidence, not new model performance: 48 affected held-out attempts and 12 development attempts pass the unchanged evaluator, recovering 33 final held-out failures and nine development failures.

## Unchanged conditions

The same 40 fixtures-v3 tasks, seed, snapshots, oracle expectations, evaluator, prompts, tool descriptions and advertised schemas, three model IDs/settings/prices, parser acceptance, five policies, transport retries, clean snapshots, limits, 300-second deadline, concurrency one, original selection rule and 90% target remain fixed. There are 100 development assignments and 300 held-out assignments. No new 95% selection threshold is introduced.

Original v3 artifacts and hashes remain untouched. Never replace interrupted results or release unknown-charge holds to fund another attempt. No extra inference pilot is necessary: the first v4 development assignments use the unchanged provider interface.

## Disclosure, verbatim on every presentation surface

Controlled rerun on the same evaluation suite. These tasks and their v3 results were inspected before the v4 amendment. This is not fresh independent validation.

## Operational gate

scripts/run_v4_study.py forecasts each batch with 50% headroom and the largest reservation against its existing allocation. It refuses a forecast beyond October 30 at 08:00 Istanbul. A process supervisor terminates active execution at that cutoff, preserves uncertain charges and writes separate completed/interrupted/not-started assignment accounting. It never invents missing run records. An incomplete v4 cannot replace the complete v3 primary report. No judge, public or safety funding may be consumed by this experiment.

The repository and deployments stay private until final publication approval. Submission target: October 30 at 18:00 Istanbul, official deadline 20:00.
