# Architecture and failure model

PaperFusion separates the LangGraph controller, model roles, the Paper2Code generator, and the Docker test executor. The controller owns task order, retries, checkpoints and evidence. The model owns decisions and edits within the declared task boundary. The executor owns test results. Reviewer and Monitor may inspect but cannot edit.

**Durability.** SQLite records completed nodes. Each role writes a receipt with an input digest and workspace manifest. If a process stops after a role finishes but before checkpointing, the receipt is reused only if inputs and files still match. If it stops during implementation, a pre-role snapshot restores the task's editable files before retrying. Paper, original project and acceptance checks are hashed. A file lock prevents concurrent writers to a run.

**Failures.** Tool launch failures, missing P2C output and Docker infrastructure errors leave the pending graph node in place. Failed acceptance checks, Reviewer rejection and Monitor rejection feed back to Implementer and consume a task attempt. Three failed attempts interrupt for a recorded retry or stop decision. SDK retries handle short transport faults separately.

**P2C generation.** A `p2c` task runs the original code generator once for a paper; later tasks reuse the hashed output. The Implementer adapts selected generated modules to the project's imports and interfaces. `direct` tasks can use paper analysis without code generation. The RRF case uses the direct path.

**Execution.** `write_file` accepts only frozen task paths. The Docker test runner mounts source and acceptance read-only, disables networking and capabilities, and receives a stripped environment. This mitigates ordinary generated-code risks; a public multi-user service would need stronger isolation and authorization.

**Acceptance.** A task completes only after independent checks pass and both read-only roles approve. Model review is evidence of judgment, not mathematical proof. The final experiment records metrics and limitations separately. RRF reports synthetic nDCG@3 and marks original benchmark reproduction false.
