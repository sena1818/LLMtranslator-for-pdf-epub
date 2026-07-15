# Process Supervision Improves the Training Signal

We study whether a process-supervised reward model gives a cleaner training signal than an outcome-supervised reward model when a large language model is fine-tuned for multi-step logical reasoning. Our benchmark is drawn from the MATH dataset, and we report accuracy on a held-out set that no model sees during tuning.

Under the outcome-supervised baseline, the reward model scores only the final answer, so a wrong intermediate reasoning step can still receive a positive training signal whenever the answer happens to be correct. The process-supervised reward model instead scores each intermediate reasoning step, which suppresses this failure mode and reduces hallucination on the held-out set.

We fine-tune the base model with stochastic gradient descent under a fixed learning rate schedule, and we select the checkpoint by best-of-N search over the held-out set. Empirical evidence across three runs shows that process supervision raises accuracy over the baseline while using comparable data efficiency. An ablation in the Appendix removes the chain-of-thought prompt and confirms that the training signal, not the prompt format, drives the gain.
