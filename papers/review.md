# New Reviews Bilingual Translation

Paper: **A2M: Trace-Optimized Agent Hijacking in the MCP Ecosystem**

Source: `new_review.txt`

Submission: ACL ARR 2026 May, Submission 1213

---

## Reviewer nAQU

### Paper Summary / 论文总结

**EN**

The paper proposes A2M (Attraction-to-Manipulation), a two-stage black-box framework for hijacking MCP-based agents by registering a malicious third-party tool. The proposed method, A2M, decomposes the attack into two stages: Attraction, which optimizes malicious tool names/descriptions to increase selection probability, and Manipulation, which uses execution-trace feedback to refine malicious tool returns after invocation. The authors instantiate four attack objectives - Cognitive Denial of Service, Information Exfiltration, Environment Integrity Compromise, and Reasoning Derailment, and evaluate on LiveMCPBench across five models.

**ZH**

本文提出了 A2M（Attraction-to-Manipulation），这是一个两阶段黑盒框架，用于通过注册恶意第三方工具来劫持基于 MCP 的 agent。A2M 将攻击分解为两个阶段：Attraction 阶段优化恶意工具的名称和描述，以提高其被选择的概率；Manipulation 阶段在工具被调用后，利用执行轨迹反馈来优化恶意工具的返回内容。作者设定了四类攻击目标：认知拒绝服务（Cognitive Denial of Service）、信息窃取（Information Exfiltration）、环境完整性破坏（Environment Integrity Compromise）和推理偏移（Reasoning Derailment），并在 LiveMCPBench 上使用五个模型进行了评估。

### Summary of Strengths / 优点总结

**EN**

- The threat model of supply-chain risk in tool integration is realistic and timely.
- The decomposition of semantic supply chain attack into selection-stage attraction and post-invocation manipulation is conceptually clean and practically useful.
- Experiments are conducted over five models and four attack scenarios.

**ZH**

- 工具集成中的供应链风险这一威胁模型现实且及时。
- 将语义供应链攻击分解为选择阶段的 attraction 和调用后的 manipulation，在概念上清晰，也具有实际价值。
- 实验覆盖了五个模型和四种攻击场景。

### Summary of Weaknesses / 缺点总结

**EN**

- The attack scenarios / attacker goals are relatively specific, e.g., cognitive denial of service and information exfiltration, and the work lacks evaluation on a general sense of hijacking, e.g., "do-anything-now" type of attack.
- The proposed method demonstrates mixed success over the existing AMA method.
- The paper lacks comparison to other tool-selection attack baselines such as ToolHijacker (https://arxiv.org/abs/2504.19793) and MPMA (https://arxiv.org/abs/2505.11154).
- The work misses discussion on instruction hierarchy as a defense to supply-chain attack.

**ZH**

- 攻击场景和攻击者目标相对具体，例如认知拒绝服务和信息窃取；论文缺少对更一般意义上“劫持”能力的评估，例如 “do-anything-now” 类型的攻击。
- 与已有 AMA 方法相比，本文方法的优势表现并不稳定，成功情况较为混合。
- 论文缺少与其他工具选择攻击 baseline 的比较，例如 ToolHijacker（https://arxiv.org/abs/2504.19793）和 MPMA（https://arxiv.org/abs/2505.11154）。
- 论文缺少关于将 instruction hierarchy 作为供应链攻击防御手段的讨论。

### Comments, Suggestions, and Typos / 评论、建议与拼写问题

**EN**

Please see strengths & weaknesses section.

**ZH**

请参见优点和缺点部分。

### Scores / 评分

**EN**

- Confidence: 3 = Pretty sure, but there's a chance I missed something. Although I have a good feel for this area in general, I did not carefully check the paper's details, e.g., the math or experimental design.
- Soundness: 3 = Acceptable: This study provides sufficient support for its main claims. Some minor points may need extra support or details.
- Excitement: 3.5
- Overall Assessment: 3 = Findings: I think this paper could be accepted to the Findings of the ACL.
- Ethical Concerns: There are no concerns with this submission.
- Needs Ethics Review: No.
- Reproducibility: 4 = They could mostly reproduce the results, but there may be some variation because of sample variance or minor variations in their interpretation of the protocol or method.
- Datasets: 1 = No usable datasets submitted.
- Software: 1 = No usable software released.

**ZH**

- 置信度：3 = 相当确定，但仍有可能遗漏了一些内容。尽管我总体上熟悉该领域，但没有仔细检查论文的细节，例如数学部分或实验设计。
- 可靠性：3 = 可接受。该研究为其主要主张提供了足够支持，但一些次要点可能需要更多支持或细节。
- 兴奋度：3.5。
- 总体评价：3 = Findings。我认为这篇论文可以被 ACL Findings 接收。
- 伦理问题：本投稿没有伦理方面的担忧。
- 是否需要伦理审查：否。
- 可复现性：4 = 结果大体可以复现，但由于样本方差或对协议/方法的细微理解差异，可能会有一些变化。
- 数据集：1 = 未提交可用数据集。
- 软件：1 = 未发布可用软件。

---

## Reviewer 9hUm

### Paper Summary / 论文总结

**EN**

This paper studies security vulnerabilities in Model Context Protocol (MCP)-based agent ecosystems. The authors argue that third-party MCP tools can influence not only tool selection through metadata, but also downstream agent reasoning through tool-return contents. To study this threat, the paper proposes A2M, an Attraction-to-Manipulation framework. The Attraction phase optimizes malicious tool names and descriptions to increase invocation probability, while the Manipulation phase uses execution traces and an Analyzer-Optimizer loop to refine adversarial return payloads. The method is evaluated on LiveMCPBench across several frontier models and four attack scenarios: Cognitive Denial of Service, Information Exfiltration, Environment Integrity Compromise, and Reasoning Derailment. Overall, the paper aims to contribute a security analysis and black-box attack framework for tool-augmented LLM agents.

**ZH**

本文研究了基于 Model Context Protocol（MCP）的 agent 生态系统中的安全漏洞。作者认为，第三方 MCP 工具不仅可以通过元数据影响工具选择，还可以通过工具返回内容影响后续的 agent 推理。为研究这一威胁，论文提出了 A2M，即 Attraction-to-Manipulation 框架。Attraction 阶段优化恶意工具名称和描述，以提高工具调用概率；Manipulation 阶段利用执行轨迹和 Analyzer-Optimizer 循环来优化对抗性返回 payload。该方法在 LiveMCPBench 上进行评估，覆盖多个前沿模型和四种攻击场景：认知拒绝服务、信息窃取、环境完整性破坏和推理偏移。总体而言，本文旨在为工具增强型 LLM agent 提供一种安全分析和黑盒攻击框架。

### Summary of Strengths / 优点总结

**EN**

- The paper addresses a timely and important problem. MCP-style tool ecosystems are becoming increasingly relevant for LLM agents, and the security risks introduced by third-party tool metadata and tool outputs are worth studying.
- The threat model is interesting. The paper highlights a setting where the user and agent may be benign, but an attacker-controlled tool can still affect agent behavior through semantic tool descriptions and malicious return payloads.
- The two-stage formulation is intuitive. Separating the attack into Attraction and Manipulation helps clarify why tool-selection attacks alone may be insufficient: a malicious tool must first be selected, but its return payload must also successfully steer the agent after invocation.
- The empirical evaluation covers multiple attack scenarios and models. The results on GLM-4.6 are especially concerning, showing large cost inflation under C-DoS and high reported ASR for IE, EIC, and RD.

**ZH**

- 论文关注了一个及时且重要的问题。MCP 风格的工具生态与 LLM agent 的关系越来越密切，由第三方工具元数据和工具输出引入的安全风险值得研究。
- 威胁模型很有意思。论文强调了一种场景：用户和 agent 都可能是良性的，但攻击者控制的工具仍然可以通过语义化工具描述和恶意返回 payload 影响 agent 行为。
- 两阶段形式化很直观。将攻击分为 Attraction 和 Manipulation 有助于说明为什么仅有工具选择攻击可能不够：恶意工具首先必须被选中，但其返回 payload 也必须在调用后成功引导 agent。
- 实证评估覆盖了多个攻击场景和模型。GLM-4.6 上的结果尤其令人担忧，显示出 C-DoS 下显著的成本膨胀，以及 IE、EIC 和 RD 中较高的报告 ASR。

### Summary of Weaknesses / 缺点总结

**EN**

- The methodological novelty over existing black-box red-teaming and tool-selection attacks is not sufficiently established. A2M mainly combines LLM-generated tool metadata, Monte Carlo selection-rate evaluation, and trace-guided payload refinement. This is a reasonable framework, but the paper does not clearly explain how it differs algorithmically from existing iterative prompt-optimization/red-teaming methods such as PAIR/TAP/AutoDAN-style approaches, or from recent tool-selection attacks such as AMA, ToolHijacker, and ToolTweak. As a result, it is unclear whether the main contribution is a new method or mainly an application of existing black-box optimization ideas to MCP agents.
- The baseline comparisons do not fully isolate the contribution of the proposed framework. For example, LLM-GA appears to use scalar fitness feedback, while A2M uses structured execution-trace feedback through the Analyzer-Optimizer loop. AMA only evaluates the metadata attraction stage and does not test post-selection manipulation. This makes it difficult to tell whether A2M's gains come from the proposed two-stage design, from richer feedback, or from different optimization budgets. Stronger comparisons such as AMA plus payload optimization, same-budget trace-aware baselines, or PAIR/TAP-style payload refinement would make the empirical claim more convincing.
- The attack-success evaluation protocol is under-specified. For IE, EIC, and RD, the paper defines a four-level score s(tau), with s=4 counted as full attack success. However, it is not clear how this score is assigned in practice: by deterministic rules, manual annotation, an LLM judge, or task-specific scripts. Since the reported ASR values depend directly on this scoring procedure, the paper should provide the exact evaluation protocol, judgment criteria, and ideally consistency checks or released scoring scripts.
- Some claims about generalization and defenses are stronger than the reported evidence supports. Although A2M transfers to unseen models in terms of malicious tool invocation, full attack success is much weaker for some models; for example, GPT-5 has non-trivial MTIR but 0 ASR for IE and EIC. Similarly, the defense evaluation only considers relatively limited defenses such as perplexity detection, a Qwen3-8B auditor, and paraphrasing. These results support the claim that simple textual defenses are insufficient, but they do not fully establish that representative agent-level defenses fail.

**ZH**

- 相比已有黑盒 red-teaming 和工具选择攻击，本文的方法新颖性尚未充分建立。A2M 主要结合了 LLM 生成的工具元数据、Monte Carlo 选择率评估以及基于轨迹的 payload 优化。这是一个合理的框架，但论文没有清楚说明它在算法上与已有迭代式 prompt 优化/red-teaming 方法（如 PAIR/TAP/AutoDAN 风格方法）或近期工具选择攻击（如 AMA、ToolHijacker、ToolTweak）有何区别。因此，目前不清楚主要贡献究竟是一种新方法，还是将已有黑盒优化思想应用到 MCP agent 上。
- baseline 比较没有充分隔离所提框架的贡献。例如，LLM-GA 似乎使用标量 fitness 反馈，而 A2M 通过 Analyzer-Optimizer 循环使用结构化执行轨迹反馈。AMA 只评估元数据 attraction 阶段，没有测试选择后的 manipulation。这使得人们难以判断 A2M 的提升来自两阶段设计、来自更丰富的反馈，还是来自不同的优化预算。更强的比较，例如 AMA 加 payload 优化、相同预算下的 trace-aware baseline，或 PAIR/TAP 风格的 payload refinement，会让实证结论更有说服力。
- 攻击成功评估协议说明不足。对于 IE、EIC 和 RD，论文定义了四级评分 s(tau)，其中 s=4 被视为完整攻击成功。然而，论文没有说明这个分数在实践中如何赋值：是通过确定性规则、人工标注、LLM judge，还是任务特定脚本。由于报告的 ASR 值直接依赖该评分过程，论文应提供准确的评估协议、判断标准，最好还应提供一致性检查或发布评分脚本。
- 关于泛化和防御的部分论断强于已有证据。虽然 A2M 在恶意工具调用方面可以迁移到未见模型，但在某些模型上完整攻击成功率要弱得多；例如 GPT-5 的 MTIR 不低，但 IE 和 EIC 的 ASR 为 0。类似地，防御评估只考虑了相对有限的防御，如 perplexity detection、Qwen3-8B auditor 和 paraphrasing。这些结果支持“简单文本防御不足”的说法，但不足以证明代表性的 agent-level 防御都失败了。

### Comments, Suggestions, and Typos / 评论、建议与拼写问题

**EN**

Please clarify whether all methods use the same optimization budget, rollout count, generator model, temperature, and access to execution traces. Please report additional C-DoS metrics beyond weighted Costx, such as unweighted token ratio, number of tool calls, wall-clock latency, or actual dollar cost. Please distinguish more explicitly between malicious tool invocation and full attack success. High MTIR alone does not necessarily imply successful agent hijacking. Please remove the editing artifact in Appendix C.2.2: "These prompts are missing from the PDF; please fill them in." Please fix the apparent rendering issue in Figure 2 around the attack guidance notation. Please provide the anonymous repository link if the paper claims that A2M is available in an anonymous repository.

**ZH**

请澄清所有方法是否使用相同的优化预算、rollout 数量、generator model、temperature，以及是否具有相同的执行轨迹访问权限。请报告除加权 Costx 之外的其他 C-DoS 指标，例如未加权 token ratio、工具调用次数、wall-clock latency 或实际美元成本。请更明确地区分恶意工具调用和完整攻击成功。高 MTIR 本身并不必然意味着成功劫持 agent。请删除 Appendix C.2.2 中的编辑残留：“These prompts are missing from the PDF; please fill them in.” 请修复 Figure 2 中 attack guidance notation 附近明显的渲染问题。如果论文声称 A2M 在匿名仓库中可用，请提供匿名仓库链接。

### Scores / 评分

**EN**

- Confidence: 4 = Quite sure. I tried to check the important points carefully. It's unlikely, though conceivable, that I missed something that should affect my ratings.
- Soundness: 2.5
- Excitement: 3.5
- Overall Assessment: 2.5 = Borderline Findings
- Ethical Concerns: There are no concerns with this submission.
- Reproducibility: 3 = They could reproduce the results with some difficulty. The settings of parameters are underspecified or subjectively determined, and/or the training/evaluation data are not widely available.
- Datasets: 3 = Potentially useful: Someone might find the new datasets useful for their work.
- Software: 2 = Documentary: The new software will be useful to study or replicate the reported research, although for other purposes it may have limited interest or limited usability. Still a positive rating.

**ZH**

- 置信度：4 = 相当确定。我认真检查了重要点。虽然仍有可能，但不太可能遗漏会影响评分的内容。
- 可靠性：2.5。
- 兴奋度：3.5。
- 总体评价：2.5 = Borderline Findings。
- 伦理问题：本投稿没有伦理方面的担忧。
- 可复现性：3 = 结果可以较困难地复现。参数设置说明不足或带有主观性，并且/或者训练/评估数据不够广泛可得。
- 数据集：3 = 可能有用。有人可能会觉得新数据集对他们的工作有帮助。
- 软件：2 = 文档型。新软件有助于研究或复现该工作，尽管用于其他目的时可能兴趣或可用性有限。仍然是正向评分。

---

## Reviewer 7yKi

### Paper Summary / 论文总结

**EN**

The paper says a successful MCP register attack needs two things, and splits them into stages: Attraction (get the malicious tool picked over the good ones) and Manipulation (once picked, steer the agent's next steps toward the attacker's goal). Their method, A2M, does both:

Phase 1 (Attraction): generate tool names/descriptions using five persuasion styles (Authority, Urgency, etc.) and keep the ones the agent actually selects.

Phase 2 (Manipulation): an "Analyzer-Optimizer" loop reads the agent's run, figures out why the attack failed, and rewrites the tool output to work better.

They test four attack goals - Cognitive Denial of Service (waste tokens/money), Information Exfiltration, Environment Integrity Compromise, and Reasoning Derailment - on LiveMCPBench with five models (GLM-4.6, Qwen3-Max, DeepSeek-V3.1, Kimi-K2, GPT-5). Results: cost inflation up to 32.4x, high success on the source model, some transfer to unseen models, and only partial blocking by existing defenses.

**ZH**

论文认为，一次成功的 MCP 注册攻击需要满足两件事，并将其拆分为两个阶段：Attraction（让恶意工具相对于正常工具被选中）和 Manipulation（一旦被选中，就将 agent 的后续步骤引向攻击者目标）。作者的方法 A2M 同时完成这两件事：

阶段 1（Attraction）：使用五种说服风格（Authority、Urgency 等）生成工具名称/描述，并保留那些实际会被 agent 选择的版本。

阶段 2（Manipulation）：一个 “Analyzer-Optimizer” 循环读取 agent 的运行过程，判断攻击为什么失败，并重写工具输出来提升效果。

作者在 LiveMCPBench 上使用五个模型（GLM-4.6、Qwen3-Max、DeepSeek-V3.1、Kimi-K2、GPT-5）测试了四类攻击目标：认知拒绝服务（浪费 token/金钱）、信息窃取、环境完整性破坏和推理偏移。结果显示：成本膨胀最高达 32.4x，在源模型上成功率较高，对未见模型有一定迁移性，现有防御只能部分阻断。

### Summary of Strengths / 优点总结

**EN**

- Important and timely target. MCP tool ecosystems are growing fast, and the "malicious tool with a poisoned output" angle is a real and understudied risk. The threat model is stated clearly.
- Sensible two-part framing. Splitting the attack into "get selected" and "then steer the agent" is a clean, well-argued idea: a good payload is useless if the tool is never picked, and a popular tool is useless if its payload is ignored.
- Trace-guided refinement is a good idea. Using the agent's own run to diagnose failures and target the next edit is smarter than random search, and the ablation shows all three components help.

**ZH**

- 目标重要且及时。MCP 工具生态正在快速发展，“带有恶意输出的恶意工具”这一角度是真实且研究不足的风险。威胁模型表述清楚。
- 两部分框架合理。将攻击拆分为“先被选中”和“再引导 agent”是一个清晰且论证充分的想法：如果工具从未被选中，再好的 payload 也无用；如果 payload 被忽略，一个经常被选中的工具也无用。
- 基于轨迹的优化是一个好想法。利用 agent 自身运行过程来诊断失败并定位下一步修改，比随机搜索更聪明；ablation 也显示三个组件都有帮助。

### Summary of Weaknesses / 缺点总结

**EN**

The authors addressed most of the previous concerns. Some are still open from last cycle:

- Robustness to deployment drift (system-prompt changes, tool renaming, different routing/competition, safety wrappers) is still not tested, and the revisions only expand the Limitations discussion of it. This was raised by two reviewers and the meta-review.
- The simple static-output heuristic baseline the authors agreed to add last cycle (e.g., AMA selection + a fixed "call me again" output) is not in the paper and is not mentioned in the revisions document.

Other concerns:

- How success is judged is still not explained. The 1-4 scoring rubric is defined (Section 4.4), and the new failure table helps, but the paper never says who or what assigns the score, like a rule, an LLM judge, or a human, or how reliable it is. This is important for trusting the ASR numbers.
- Headline numbers are cherry-picked; no variance. "Up to 32.4x" is one best case on the source model; on other models it drops to 2-3x. The benchmark has only 95 tasks (fewer per attack), so percentages are shaky, and there are still no repeated runs or confidence intervals. The "severity" framing should be toned down.

**ZH**

作者已经解决了大部分上一轮问题。但上一轮的一些问题仍然存在：

- 对 deployment drift 的鲁棒性仍未测试，包括 system prompt 变化、工具重命名、不同 routing/competition、安全 wrapper 等；修订稿只是扩展了 Limitations 中的讨论。这个问题此前由两位 reviewer 和 meta-review 提出过。
- 作者上一轮同意加入的简单 static-output heuristic baseline（例如 AMA selection + 固定的 “call me again” 输出）没有出现在论文中，也没有在 revision document 中提到。

其他问题：

- 仍然没有解释成功是如何判定的。论文定义了 1-4 的评分 rubric（Section 4.4），新的 failure table 也有帮助，但论文从未说明是谁或什么机制给出该分数，例如规则、LLM judge、人类，或其可靠性如何。这对于信任 ASR 数字非常重要。
- 主要结果数字有 cherry-picking，而且没有 variance。“Up to 32.4x” 是源模型上的一个最佳情况；在其他模型上降到 2-3x。benchmark 只有 95 个任务，每种攻击的任务更少，因此百分比并不稳健，而且仍然没有 repeated runs 或 confidence intervals。论文中关于 “severity” 的表述应当降调。

### Comments, Suggestions, and Typos / 评论、建议与拼写问题

**EN**

A leftover draft note in line 851-852.

**ZH**

第 851-852 行有残留的草稿注释。

### Scores / 评分

**EN**

- Confidence: 4 = Quite sure. I tried to check the important points carefully. It's unlikely, though conceivable, that I missed something that should affect my ratings.
- Soundness: 4 = Strong: This study provides sufficient support for all of its claims. Some extra experiments could be nice, but not essential.
- Excitement: 3 = Interesting: I might mention some points of this paper to others and/or attend its presentation in a conference if there's time.
- Overall Assessment: 2.5 = Borderline Findings
- Ethical Concerns: There are no concerns with this submission.
- Needs Ethics Review: No.
- Reproducibility: 4 = They could mostly reproduce the results, but there may be some variation because of sample variance or minor variations in their interpretation of the protocol or method.
- Datasets: 3 = Potentially useful: Someone might find the new datasets useful for their work.
- Software: 3 = Potentially useful: Someone might find the new software useful for their work.

**ZH**

- 置信度：4 = 相当确定。我认真检查了重要点。虽然仍有可能，但不太可能遗漏会影响评分的内容。
- 可靠性：4 = 强。该研究为所有主张提供了足够支持。额外实验会更好，但不是必要的。
- 兴奋度：3 = 有意思。如果有时间，我可能会向别人提到这篇论文的一些点，或参加其会议报告。
- 总体评价：2.5 = Borderline Findings。
- 伦理问题：本投稿没有伦理方面的担忧。
- 是否需要伦理审查：否。
- 可复现性：4 = 结果大体可以复现，但由于样本方差或对协议/方法的细微理解差异，可能会有一些变化。
- 数据集：3 = 可能有用。有人可能会觉得新数据集对他们的工作有帮助。
- 软件：3 = 可能有用。有人可能会觉得新软件对他们的工作有帮助。

---

## Reviewer v7oi

### Paper Summary / 论文总结

**EN**

This paper introduces A2M (Attraction-to-Manipulation), a two-stage black-box attack framework designed for the MCP (Model Context Protocol) ecosystem to systematically "hijack" tool-calling agents. The core argument is that in MCP scenarios, an attack extends beyond merely "inducing tool selection" (Attraction) to "inducing the tool to return content that manipulates subsequent reasoning" (Manipulation); while coupled, these two stages can be optimized independently. Phase I employs five persuasion strategies to generate tool metadata and uses Monte Carlo rollouts to evaluate selection rates. Phase II utilizes an Analyzer-Optimizer architecture to iteratively refine the malicious payload based on execution traces, incorporating specialized fitness functions for four attack scenarios: C-DoS, IE, EIC, and RD. Experiments conducted on LiveMCPBench across five state-of-the-art models demonstrate that A2M significantly outperforms Zero-Shot and LLM-GA baselines in all attack scenarios. Furthermore, A2M exhibits cross-model transferability and proves resistant to existing defenses (such as PPL detection, LLM Auditor, and paraphrase-based defenses), which offer only partial mitigation.

**ZH**

本文介绍了 A2M（Attraction-to-Manipulation），这是一个为 MCP（Model Context Protocol）生态系统设计的两阶段黑盒攻击框架，用于系统性地“劫持”工具调用型 agent。其核心论点是，在 MCP 场景中，攻击不仅仅是“诱导工具选择”（Attraction），还包括“诱导工具返回能够操纵后续推理的内容”（Manipulation）；这两个阶段虽然在执行上相互关联，但可以独立优化。第一阶段使用五种说服策略生成工具元数据，并通过 Monte Carlo rollout 评估选择率。第二阶段使用 Analyzer-Optimizer 架构，基于执行轨迹迭代优化恶意 payload，并为四种攻击场景 C-DoS、IE、EIC 和 RD 设计了专门的 fitness function。在 LiveMCPBench 上对五个 state-of-the-art 模型进行的实验表明，A2M 在所有攻击场景中显著优于 Zero-Shot 和 LLM-GA baseline。此外，A2M 具有跨模型迁移性，并对现有防御（如 PPL detection、LLM Auditor 和 paraphrase-based defenses）表现出抗性，而这些防御只能提供部分缓解。

### Summary of Strengths / 优点总结

**EN**

- MCP and tool-augmented agents are emerging as the de facto infrastructure for agent systems. The paper addresses the issue of agents placing excessive trust in third-party tool metadata and return values - a perspective with significant practical relevance. It highlights a critical observation for security assessment: tool return values are often treated as "trusted environment feedback" rather than ordinary, untrusted text input.
- The study defines four attack objectives - C-DoS, Information Exfiltration, Environment Integrity Compromise, and Reasoning Derailment - covering resource exhaustion, data leakage, environmental tampering, and reasoning deviation. This approach offers a more comprehensive scope than "metadata attacks" that focus solely on whether a tool is invoked.
- Experiments covered models such as GLM-4.6, Qwen3-Max, DeepSeek-V3.1, Kimi-K2-0905, and GPT-5, utilizing 95 tasks, 70 MCP servers, and 527 tools from the LiveMCPBench dataset.
- On GLM-4.6, the A2M method demonstrated significant improvements over zero-shot and LLM-GA baselines, achieving results such as a 32.4x increase for C-DoS and Attack Success Rates (ASR) of 65.9 for IE, 64.3 for EIC, and 92.9 for RD. These findings support the fundamental conclusion that "trace-guided refinement" is superior to "one-shot generation."

**ZH**

- MCP 和工具增强型 agent 正在成为 agent 系统事实上的基础设施。论文关注了 agent 对第三方工具元数据和返回值过度信任的问题，这一视角具有很强的实践相关性。论文强调了一个对安全评估很关键的观察：工具返回值通常被视为“可信环境反馈”，而不是普通的不可信文本输入。
- 研究定义了四类攻击目标：C-DoS、信息窃取、环境完整性破坏和推理偏移，覆盖资源耗尽、数据泄露、环境篡改和推理偏离。相比只关注工具是否被调用的“metadata attacks”，这一范围更全面。
- 实验覆盖了 GLM-4.6、Qwen3-Max、DeepSeek-V3.1、Kimi-K2-0905 和 GPT-5 等模型，并使用了 LiveMCPBench 数据集中的 95 个任务、70 个 MCP server 和 527 个工具。
- 在 GLM-4.6 上，A2M 相比 zero-shot 和 LLM-GA baseline 有显著提升，例如 C-DoS 达到 32.4x 增长，IE、EIC 和 RD 的攻击成功率（ASR）分别为 65.9、64.3 和 92.9。这些结果支持了一个基本结论：基于轨迹的优化优于 one-shot generation。

### Summary of Weaknesses / 缺点总结

**EN**

- The "Attraction" phase employs five types of persuasion strategies: Authority, Urgency, Comprehensiveness, Resource Optimality, and Security. These appear to be manually designed prompt categories rather than novel algorithms. Is it possible that one or two strategies drive the majority of the performance gains, rendering the others redundant? I suggest conducting an analysis of the individual contribution or ranking of these five strategies to clarify which are critical and which might be superfluous.
- Table 1 compares the method only against Zero-Shot and LLM-GA; specialized "Attraction" attack methods from the same period - such as ToolHijacker and MPMA - were not included in the direct comparison.
- Is the number of Monte Carlo rollouts (with Kroll=3) sufficient to provide a stable estimate of the selection rate? Has a sensitivity analysis been performed regarding the results when varying the Kroll value?
- Details regarding inference hyperparameters (temperature, sampling strategy, etc.) for the various models are missing; please clarify whether consistent settings were used across all models.

**ZH**

- “Attraction” 阶段使用了五类说服策略：Authority、Urgency、Comprehensiveness、Resource Optimality 和 Security。这些看起来更像人工设计的 prompt 类别，而不是新算法。是否可能只有一两种策略贡献了大部分性能提升，从而使其他策略变得冗余？建议分析这五种策略的单独贡献或排序，以明确哪些是关键的，哪些可能是多余的。
- Table 1 只将本文方法与 Zero-Shot 和 LLM-GA 比较；同期专门针对 “Attraction” 的攻击方法，例如 ToolHijacker 和 MPMA，没有被纳入直接比较。
- Monte Carlo rollout 数量（Kroll=3）是否足以稳定估计选择率？是否做过改变 Kroll 值时结果变化的敏感性分析？
- 缺少不同模型的 inference hyperparameters 细节，例如 temperature、sampling strategy 等；请澄清所有模型是否使用了一致设置。

### Comments, Suggestions, and Typos / 评论、建议与拼写问题

**EN**

None.

**ZH**

无。

### Scores / 评分

**EN**

- Confidence: 2 = Willing to defend my evaluation, but it is fairly likely that I missed some details, didn't understand some central points, or can't be sure about the novelty of the work.
- Soundness: 3 = Acceptable: This study provides sufficient support for its main claims. Some minor points may need extra support or details.
- Excitement: 3 = Interesting: I might mention some points of this paper to others and/or attend its presentation in a conference if there's time.
- Overall Assessment: 2 = Resubmit next cycle: I think this paper needs substantial revisions that can be completed by the next ARR cycle.
- Ethical Concerns: There are no concerns with this submission.
- Reproducibility: 3 = They could reproduce the results with some difficulty. The settings of parameters are underspecified or subjectively determined, and/or the training/evaluation data are not widely available.
- Datasets: 1 = No usable datasets submitted.
- Software: 3 = Potentially useful: Someone might find the new software useful for their work.

**ZH**

- 置信度：2 = 我愿意为我的评价辩护，但我很可能遗漏了一些细节、没有理解某些核心点，或者无法确定该工作的 novelty。
- 可靠性：3 = 可接受。该研究为其主要主张提供了足够支持，但一些次要点可能需要更多支持或细节。
- 兴奋度：3 = 有意思。如果有时间，我可能会向别人提到这篇论文的一些点，或参加其会议报告。
- 总体评价：2 = 下个周期重投。我认为这篇论文需要较大修改，而这些修改可以在下一个 ARR 周期内完成。
- 伦理问题：本投稿没有伦理方面的担忧。
- 可复现性：3 = 结果可以较困难地复现。参数设置说明不足或带有主观性，并且/或者训练/评估数据不够广泛可得。
- 数据集：1 = 未提交可用数据集。
- 软件：3 = 可能有用。有人可能会觉得新软件对他们的工作有帮助。

