# External data

## SMS Spam Collection v.1

- Source: Tiago A. Almeida and José María Gómez Hidalgo, UCI Machine Learning Repository, dataset 228.
- DOI: <https://doi.org/10.24432/C5CC84>
- License: CC BY 4.0.
- Files: the original `SMSSpamCollection` (tab-separated `label<TAB>text`) and `readme`.
- Archive SHA-256: `1587ea43e58e82b14ff1f5425c88e17f8496bfcdb67a583dbff9eefaf9963ce3`.
- Purpose: reproducible training and evaluation of the English SMS spam gate. It is an
  external research corpus, not a Chinese campus-notice corpus.

The raw messages were not rewritten. The training script removes exact duplicate
rows before splitting and reports all metrics on a stratified holdout set.

