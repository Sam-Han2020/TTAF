# Third-Party Notices

TTAF builds on and adapts code from the following projects.

## GraCeFul

- Project: **Gracefully Filtering Backdoor Samples for Generative Large
  Language Models without Retraining**
- Repository: <https://github.com/ZrW00/GraceFul>
- License: GNU General Public License v3.0

The TTAF entry point and generative OpenBackdoor workflow were developed from
the GraCeFul codebase and subsequently modified for TTAF.

## OpenBackdoor

- Project: **OpenBackdoor: An Open Toolkit for Textual Backdoor Attack and
  Defense**
- Repository: <https://github.com/thunlp/OpenBackdoor>
- License: Apache License 2.0
- License text: [`LICENSES/Apache-2.0.txt`](LICENSES/Apache-2.0.txt)

Portions of the local `openbackdoor/` package originate from or are adapted
from OpenBackdoor. Files have been modified to support generative causal LLMs,
paper-specific attacks, and TTAF filtering.

## Additional Dependencies

Third-party Python packages installed through `requirements.txt` remain subject
to their own licenses. Dataset notices are maintained separately in
`datasets/README.md`.
