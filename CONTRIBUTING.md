# Contributing

Cost to Done prioritizes correctness, reproducibility, and direct developer utility. Contributions are welcome for validated import formats, verification design, task qualification, CLI ergonomics, cost accounting, and clear reporting.

Run the zero-dependency regression suite with:

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
```

For substantive changes, include a failing regression test, then the implementation, plus an explanation of the measurement contract affected. Use exact pinned test fixtures for external API adapters. Avoid real-provider performance comparisons without raw artifacts and a documented execution environment. Do not commit provider credentials, user prompts, proprietary repositories, or actual personal data.

A passing unit test proves local behavior under tested conditions. It is not by itself an empirical result about AI agents.
