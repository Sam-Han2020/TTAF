# Processed Question-Answering Datasets

This directory contains the processed and sampled subsets used by the TTAF
experiments. These files are not the complete raw upstream datasets.

## Included Splits

| Dataset | Train | Dev | Test | Local format |
| --- | ---: | ---: | ---: | --- |
| WebQA | 3,401 | 377 | 2,032 | Hugging Face Arrow |
| FreebaseQA | 5,000 | 400 | 2,000 | JSON |
| NQ | 5,000 | 400 | 2,000 | JSON |
| CoQA | 5,000 | 400 | 498 | Hugging Face `save_to_disk` |

WebQA contains 3,778 examples in its stored training split. The project loader
uses `dev_rate=0.1` to obtain the reported 3,401 training and 377 development
examples.

## Sources and Licenses

- **WebQA / WebQuestions** — introduced by Berant et al. (2013) and released
  through Stanford SEMPRE under CC BY 4.0:
  <https://nlp.stanford.edu/software/sempre/>.
- **FreebaseQA** — introduced by Jiang et al. (2019); the official dataset is
  distributed under CC BY 4.0:
  <https://github.com/kelvin-jiang/FreebaseQA>.
- **Natural Questions (NQ)** — introduced by Kwiatkowski et al. (2019). The
  official data download states CC BY-SA 3.0 terms:
  <https://ai.google.com/research/NaturalQuestions/download>.
- **CoQA** — introduced by Reddy et al. (2019). CoQA contains passages from
  several sources with source-specific licenses; consult the official license
  section before redistribution or downstream use:
  <https://stanfordnlp.github.io/coqa/>.

The preprocessing and sampling performed for TTAF do not replace the upstream
license terms. Users are responsible for complying with the corresponding
dataset licenses and attribution requirements.
