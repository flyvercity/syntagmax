---
name: sc.critique.spec.md
description: Challenge the specification and implementation plan through two distinct expert lenses.
---

## Goal

Challenge the specification and implementation plan through two distinct expert lenses BEFORE committing to implementation. The **Product Lens** evaluates whether the right problem is being solved in the right way for users. The **Engineering Lens** evaluates whether the technical approach is sound, scalable, and free of hidden risks. This dual review prevents costly mid-implementation pivots and catches strategic and technical blind spots early.

## Operating Constraints

**CONSTRUCTIVE CHALLENGE**: The goal is to strengthen the spec and plan, not to block progress. Every critique item must include a constructive suggestion for improvement.

1. **Product Lens Review** (CEO/Product Lead Perspective):

   Adopt the mindset of an experienced product leader who cares deeply about user value, market fit, and business impact. Evaluate:

   #### 1a. Problem Validation
   - Is the problem statement clear and well-defined?
   - Is this solving a real user pain point, or is it a solution looking for a problem?
   - What evidence supports the need for this feature? (user research, data, customer requests)
   - Is the scope appropriate — not too broad (trying to do everything) or too narrow (missing the core value)?

   #### 1b. User Value Assessment
   - Does every user story deliver tangible user value?
   - Are the acceptance criteria written from the user's perspective (outcomes, not implementation)?
   - Is the user journey complete — or are there gaps where users would get stuck?
   - What's the simplest version that would deliver 80% of the value? (MVP analysis)
   - Are there unnecessary features that add complexity without proportional value?

   #### 1c. Alternative Approaches
   - Could a simpler solution achieve the same outcome?
   - Are there existing tools, libraries, or services that could replace custom implementation?
   - What would a competitor's approach look like?
   - What would happen if this feature were NOT built? What's the cost of inaction?

   #### 1d. Edge Cases & User Experience
   - What happens when things go wrong? (error states, empty states, loading states)
   - How does this feature interact with existing functionality?
   - Are accessibility considerations addressed?
   - Is the feature discoverable and intuitive?
   - What are the onboarding/migration implications for existing users?

   #### 1e. Success Measurement
   - Are the success criteria measurable and time-bound?
   - How will you know if this feature is successful after launch?
   - What metrics should be tracked?
   - What would trigger a rollback decision?

2. **Engineering Lens Review** (Staff Engineer Perspective):

   Adopt the mindset of a senior staff engineer who has seen projects fail due to hidden technical risks. Evaluate:

   #### 2a. Architecture Soundness
   - Does the architecture follow established patterns for this type of system?
   - Are boundaries and interfaces well-defined (separation of concerns)?
   - Is the architecture testable at each layer?
   - Are there circular dependencies or tight coupling risks?
   - Does the architecture support future evolution without major refactoring?

   #### 2b. Failure Mode Analysis
   - What are the most likely failure modes? (network failures, data corruption, resource exhaustion)
   - How does the system degrade gracefully under each failure mode?
   - What happens under peak load? Is there a scaling bottleneck?
   - What are the blast radius implications — can a failure in this feature affect other parts of the system?
   - Are retry, timeout, and circuit-breaker strategies defined?

   #### 2c. Security & Privacy Review
   - What is the threat model? What attack vectors does this feature introduce?
   - Are trust boundaries clearly defined (user input, API responses, third-party data)?
   - Is sensitive data handled appropriately (encryption, access control, retention)?
   - Are there compliance implications (GDPR, SOC2, HIPAA)?
   - Is the principle of least privilege followed?

   #### 2d. Performance & Scalability
   - Are there potential bottlenecks in the data flow?
   - What are the expected data volumes? Will the design handle 10x growth?
   - Are caching strategies appropriate and cache invalidation well-defined?
   - Are database queries optimized (indexing, pagination, query complexity)?
   - Are there resource-intensive operations that should be async or batched?

   #### 2e. Testing Strategy
   - Is the testing plan comprehensive (unit, integration, E2E)?
   - Are the critical paths identified for priority testing?
   - Is the test data strategy realistic?
   - Are there testability concerns (hard-to-mock dependencies, race conditions)?
   - Is the test coverage target appropriate for the risk level?

   #### 2f. Operational Readiness
   - Is observability planned (logging, metrics, tracing)?
   - Are alerting thresholds defined?
   - Is there a rollback strategy?
   - Are database migrations reversible?
   - Is the deployment strategy clear (blue-green, canary, feature flags)?

   #### 2g. Dependencies & Integration Risks
   - Are third-party dependencies well-understood (stability, licensing, maintenance)?
   - Are integration points with existing systems well-defined?
   - What happens if an external service is unavailable?
   - Are API versioning and backward compatibility considered?

3. **Cross-Lens Synthesis**:
   Identify items where both lenses converge (these are highest priority):
   - Product simplification that also reduces engineering risk
   - Engineering constraints that affect user experience
   - Scope adjustments that improve both value delivery and technical feasibility

4. **Severity Classification**:
   Classify each finding:

   - 🎯 **Must-Address**: Blocks proceeding to implementation. Critical product gap, security vulnerability, or architecture flaw.
   - 💡 **Recommendation**: Strongly suggested improvement that would significantly improve quality, value, or risk profile. Should be addressed but won't block progress.
   - 🤔 **Question**: Ambiguity or assumption that needs stakeholder input. Cannot be resolved by the development team alone.

7. **Generate Critique Report**:
   Ensure the directory `docs/critiques/` exists (create it if necessary), then create the critique report. If critique report already exists, do not overwrite, create a new file. The report must include:

   - **Executive Summary**: Overall assessment and readiness to proceed
   - **Product Lens Findings**: Organized by subcategory
   - **Engineering Lens Findings**: Organized by subcategory
   - **Cross-Lens Insights**: Items where both perspectives converge
   - **Findings Summary Table**: All items with ID, lens, severity, summary, suggestion

   **Findings Table Format**:
   | ID | Lens | Severity | Category | Finding | Suggestion |
   |----|------|----------|----------|---------|------------|
   | P1 | Product | 🎯 | Problem Validation | No evidence of user need | Conduct 5 user interviews or reference support tickets |
   | E1 | Engineering | 💡 | Failure Modes | No retry strategy for API calls | Add exponential backoff with circuit breaker |
   | X1 | Both | 🎯 | Scope × Risk | Feature X adds complexity with unclear value | Defer to v2; reduces both scope and technical risk |

8. **Provide Verdict**:
   Based on findings, provide one of:
   - ⚠️ **PROCEED WITH UPDATES**: Must-address items found but are resolvable.
   - 🛑 **RETHINK**: Fundamental product or architecture concerns. Recommend revisiting the spec.

9. **Offer Remediation**:
   For each must-address item and recommendation:
   - Provide a specific suggested edit to the spec.
   - Ask: "Would you like me to apply these changes? (all / select / none)"
   - If user approves, apply changes to the relevant files
   - After applying changes, recommend re-running critique` to verify.

