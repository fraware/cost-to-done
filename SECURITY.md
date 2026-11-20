# Security

This repository currently validates and renders local receipt data; it does **not** run external agent commands. Treat JSONL receipt files, Harbor results, and manifests as untrusted input.

Do not run future real-agent evaluations in the same execution environment that holds repository secrets, long-lived production credentials, or private acceptance tests. Always scope provider keys and outbound network access. The executable verifier and acceptance tests must be inaccessible for agent modification or inspection during task execution.

Report a security issue privately through a GitHub security advisory if the repository supports private vulnerability reporting. Otherwise, contact the maintainer directly through the GitHub profile. Do not publish executable exploits, keys, or private logs in public issues.
