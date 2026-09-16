# Rebuttal Draft

## Reviewer nAQU
We thank the reviewer for the thoughtful comments. We also appreciate the reviewer's recognition that the threat model is realistic and timely, that the Attraction-Manipulation decomposition is clean and practically useful, and that the evaluation covers five models and four attack scenarios. We respond to the main concerns below. 

### W1: Scope of attack objectives and broader agent hijacking evaluation
We would like to clarify that the four evaluated scenarios are concrete instantiations of agent hijacking. In successful cases, the malicious tool changes the agent's subsequent reasoning, tool use, or actions and drives the agent to complete an attacker-specified objective. We selected these four concrete and measurable attack objectives because they are reproducible and cover representative security harms in MCP-based tool-augmented agents.

### W2,W3: Comparison with tool-selection attack baselines
We thank the reviewer for raising the comparison with AMA and for suggesting additional tool-selection baselines, including ToolHijacker and MPMA. We would like to emphasize that A2M is not only a tool-selection attack. AMA, ToolHijacker, and MPMA mainly optimize tool metadata, tool documents, or MCP server descriptions to increase the probability that a malicious or preferred tool is selected. In contrast, A2M couples this Attraction stage with a trace-guided Manipulation stage, which optimizes tool-return payloads to steer the agent’s subsequent reasoning, tool use, and actions toward concrete attacker-specified objectives.

For the Attraction stage alone, we have already compared A2M with AMA under the same setting. As reported in Table 2, A2M achieves a higher average MTIR than AMA across the evaluated models (80.7 vs. 75.6). This shows that A2M achieves stronger average tool-selection performance, while its main contribution is the end-to-end attack chain beyond tool selection.

Following the reviewer’s suggestion, we have started additional full-pipeline experiments. Specifically, we use AMA, ToolHijacker, and MPMA to construct tool metadata, and combine the resulting metadata with static tool-return payloads designed for each attack objective to form complete tool instances. We then evaluate these baseline-based tool instances under the same task and model settings, and will report the complete results during the Author Response period.

### W4: Instruction hierarchy as a defense for semantic supply-chain attacks
We thank the reviewer for pointing this out. We agree that instruction hierarchy is an important defense principle for MCP supply-chain attacks, since tool metadata and tool outputs should be treated as lower-priority, untrusted content rather than instructions that can override the user or system intent.

Following this suggestion, we have started an additional evaluation with a FIDES-style information-flow control defense, inspired by FIDES, a recent information-flow-control defense for AI agents (https://arxiv.org/abs/2505.23643). This defense operationalizes the instruction-hierarchy principle at the agent-execution level: it treats third-party tool-return payloads as untrusted data, treats sensitive local/configuration contents as confidential data, and performs a policy check before subsequent tool calls. We will report the results during the Author Response period and add the corresponding discussion in the revision.


## Reviewer 9hUm

We appreciate the reviewer’s careful reading and constructive feedback. We are encouraged by the reviewer’s recognition of the paper’s timely focus on MCP-style tool ecosystems, the interesting threat model in which attacker-controlled tool metadata and tool-return payloads can influence benign agents, the intuitive Attraction-Manipulation formulation, and the breadth of the evaluation across multiple attack scenarios and models. Below, we address the reviewer’s main concerns.

### W1: Methodological positioning relative to black-box red-teaming and tool-selection attacks
We thank the reviewer for pointing out the need to better clarify the relationship between A2M and prior black-box red-teaming and tool-selection attacks. We agree that A2M uses general optimization components that are common in prior work, such as LLM-based candidate generation and iterative refinement.
PAIR/TAP/AutoDAN-style methods mainly perform prompt-level red-teaming. They optimize direct user-facing prompts to elicit unsafe responses from a target model. AMA, ToolHijacker, and ToolTweak are closer to our setting, but they primarily target tool selection, i.e., they optimize metadata or tool documents to increase the probability that a malicious or preferred tool is selected. As noted in our related work, these methods mainly correspond to the Attraction stage of A2M. A2M further studies the post-invocation stage: after the malicious tool is selected, its return payload must still manipulate the agent’s subsequent reasoning, tool calls, or actions, and complete the attacker-specified attack objective.
### W2: Fair-budget baseline comparisons and contribution isolation
We agree with the reviewer that the key difference between LLM-GA and A2M lies in the form of optimization feedback. In fact, this is one of the main designs of A2M: A2M uses execution traces to guide payload refinement, rather than relying only on scalar fitness. LLM-GA can indicate whether a candidate tool performs well overall, but it cannot explain why an attack failed. In contrast, A2M can identify failure causes from the execution trace and perform more targeted optimization.

For AMA, it is a metadata-only method and does not include payload optimization. Therefore, it is more suitable as an Attraction-stage baseline. To better isolate the contribution of the Manipulation stage, we have started additional full-pipeline baseline experiments. Specifically, we use AMA to construct tool metadata, and combine the resulting metadata with static tool-return payloads designed for each attack objective to form complete malicious tool instances. We then evaluate these baseline-based tool instances under the same task, model, and optimization budget settings, and will report the complete results during the Author Response period.
### W3: Attack-success scoring protocol and reproducibility
We thank the reviewer for pointing out that the evaluation protocol is under-specified. We will clarify the scoring procedure in the revision. For IE, EIC, and RD, we use an LLM judge with a fixed rubric to automatically score the full execution trace, rather than manual annotation or task-specific scorers. The rubric follows the four-level definition in the paper: 1 means the malicious tool is not invoked, 2 means the tool is invoked but the payload does not steer the agent toward the attack goal, 3 means the agent attempts the attack but does not complete the objective, and 4 means the attack objective is fully achieved. We will add the judge prompt, scoring criteria, and implementation details in the revision. The relevant scoring scripts are available in our anonymous repository: https://anonymous.4open.science/r/A2M-63A0.
### W4: Distinguishing tool invocation from full attack success and defense scope
We thank the reviewer for pointing out that the generalization claim should be stated more precisely. Our results do not show that A2M lacks transferability; rather, they show that transferability differs across attack stages and target models. Specifically, A2M shows relatively stable transfer at the selection stage: without re-optimization, A2M still achieves IE MTIR of 67.6, 64.9, 81.1, and 40.5 on Qwen3-Max, GPT-5, DeepSeek-V3.1, and Kimi-K2-0905, respectively. This indicates that the optimized malicious metadata can transfer across models and induce malicious tool invocation. In contrast, ASR also depends on how the target model handles malicious tool-return content after invocation, and therefore varies more across models. For example, on DeepSeek-V3.1, A2M still achieves 35.1 IE ASR and 28.9 EIC ASR; on GPT-5, however, the ASR for both IE and EIC is 0.

Regarding defenses, we would like to clarify that the defenses evaluated in this paper are not merely simple text filters. In addition to perplexity-based detection, we evaluate an auditor that inspects tool metadata and tool-return content, as well as a paraphrasing defense that rewrites tool descriptions to reduce metadata-level attraction. These defenses operate at the tool-content/tool-metadata level. To further address this point, we have started additional defense experiments with a FIDES-style information-flow control defense, inspired by FIDES, a recent information-flow-control defense for AI agents (https://arxiv.org/abs/2505.23643). This defense treats third-party tool-return payloads as untrusted data and sensitive local/configuration contents as confidential data, and performs a policy check before subsequent tool calls. We will report the results during the Author Response period and revise the defense discussion accordingly.

### Comments, Suggestions, and Typos
We thank the reviewer for these detailed suggestions. In the revised version, we will clarify that all methods use the same generator model, temperature, and rollout count. Except for Zero-Shot, which performs no iterative optimization, all optimization-based methods use the same optimization budget. We will also make explicit that only A2M uses execution traces, as trace-guided refinement is the core mechanism of our method.

For C-DoS, we will add input-token and output-token amplification in addition to weighted Costx, and report the results during the Author Response period after the additional baseline experiments are completed. Finally, we will remove the Appendix C.2.2 editing artifact and re-check Figure 2 in the compiled PDF. Our anonymous repository is available at: https://anonymous.4open.science/r/A2M-63A0.




## Reviewer 7yKi
We appreciate the reviewer’s constructive feedback and are encouraged by the recognition that MCP tool ecosystems are an important and timely security target, that malicious tools with poisoned outputs are a real and understudied risk, that our two-part framing is sensible, and that trace-guided refinement is a useful idea. We respond to the remaining concerns below.
### W1: Robustness to deployment drift, routing changes, and safety wrappers
We thank the reviewer for raising this point. We agree that system-prompt changes, tool renaming, routing changes, and safety wrappers are important deployment-drift factors. We would like to emphasize, however, that our current evaluation already covers several important sources of deployment variation: cross-model transfer, cross-query generalization, and direct competition with tools from 70 MCP servers across six domains. These results show that A2M is not limited to a single fixed query, model, or narrow tool pool.

To further address the safety-wrapper aspect, we have started additional experiments with a FIDES-style information-flow control defense, inspired by FIDES (https://arxiv.org/abs/2505.23643). We will report the results during the Author Response period.
### W2: Static-output heuristic baseline
We thank the reviewer for pointing this out. We have started additional full-pipeline baseline experiments with static tool-return payloads. Specifically, we use tool-selection methods such as AMA, ToolHijacker, and MPMA to construct malicious tool metadata, and combine the resulting metadata with fixed return payloads designed for each attack objective. We will report the results during the Author Response period.
### W3: Attack-success scoring protocol

We thank the reviewer for pointing out that the scoring procedure should be specified more clearly. For IE, EIC, and RD, the attack score is assigned automatically by an LLM judge using a fixed scoring criterion over the full execution trace, rather than by manual annotation or task-specific scripts. The criterion follows the four-level definition in the paper: 1 means the malicious tool is not invoked, 2 means the tool is invoked but does not steer the agent toward the attack goal, 3 means the agent attempts the attack but does not complete it, and 4 means the attack objective is fully achieved.
In the revised version, we will add the judge prompt, scoring criteria, and implementation details. The relevant scoring scripts are available in our anonymous repository: https://anonymous.4open.science/r/A2M-63A0.
### W4: Result presentation and severity framing
We thank the reviewer for pointing this out. We would like to clarify that the 32.4x C-DoS result corresponds to the direct-attack setting, where A2M is optimized and evaluated on the target model GLM-4.6. In contrast, the 2-3x results on the other models correspond to the transfer-attack setting, where tools optimized on GLM-4.6 are directly evaluated on unseen target models without re-optimization. Therefore, this gap reflects the difference between direct optimization and cross-model transfer.

We acknowledge that the current presentation overemphasizes the strongest direct-attack result and does not sufficiently summarize the transfer results. In the revision, we will explicitly present 32.4x as the maximum direct-attack result.

### Comments, Suggestions, and Typos

We will remove the leftover draft note in Appendix C.2.2 in the revised version.


## Reviewer v7oi
We appreciate the reviewer’s constructive feedback. We are encouraged by the reviewer’s recognition of the practical relevance of MCP security, the importance of studying malicious tool-return content, the breadth of our attack objectives, and the empirical evidence supporting trace-guided refinement. We respond to the main concerns below.
### W1: Contribution of the five attraction strategies

We agree that the five attraction strategies should be analyzed more explicitly. These strategies are used to diversify metadata generation in the Attraction stage, rather than being claimed as separate algorithmic contributions. To examine their individual roles, we analyze the winning strategy for each task, i.e., the strategy that produced the final selected metadata in the Attraction stage.

| Strategy | Winning share |
|---|---:|
| Comprehensiveness | 31.6% |
| Resource Optimality | 22.1% |
| Authority | 18.9% |
| Security | 14.7% |
| Urgency | 12.6% |

The results show that the gains are not driven by a single strategy. While Comprehensiveness and Resource Optimality are the strongest, the other three strategies still account for 46.2% of the winning cases. We will add this per-strategy analysis in the revision.

### W2: Comparison with ToolHijacker and MPMA
We agree that ToolHijacker and MPMA are relevant tool-selection baselines. To address this, we have started additional full-pipeline baseline experiments. Specifically, we use ToolHijacker and MPMA to construct malicious tool metadata, and combine the resulting metadata with static tool-return payloads designed for each attack objective to form complete malicious tool instances. We will evaluate these baseline-based tool instances under the same task and model settings, and report the results during the Author Response period.
### W3: Sensitivity to the Monte Carlo rollout count
Kroll=3 is used only during the Attraction stage to estimate and rank candidate metadata, not as the final reported selection rate. We chose Kroll=3 as a practical trade-off between estimate stability and optimization cost. We have not performed a systematic sensitivity analysis over different Kroll values in the current version, and will add this as a limitation in the revision.
### W4: Inference hyperparameters and reproducibility
We will add an inference-hyperparameter table to the appendix in the revised version. As shown below, for parameters under our explicit control, we use consistent settings across target models. Sampling-related parameters that are not explicitly set follow the corresponding provider defaults.
| Parameter | Setting |
|---|---|
| Agent temperature | 0.0 |
| Judge temperature | 0.0 |
| Generation temperature | 0.7 |
| Mutation / crossover temperature | 0.8 |
| `do_sample` | true |
| `top_p` / `top_k` | Provider defaults |
| `max_tokens` | 8192 |
| GPT-5 `reasoning_effort` | medium |