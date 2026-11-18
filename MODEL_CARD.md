# Model card

## Notice category model

- Task: seven-way Chinese campus-notice routing.
- Input: public notice title plus up to 2,500 characters of body text.
- Representation: character-level TF-IDF, 1–4 grams, `min_df=2`, 30,000 features.
- Learned model: multinomial logistic regression, `class_weight="balanced"`, `C=3`.
- Hybrid guard: after the learned model, explicit taxonomy phrases can override a drifted
  label. The original model label and probability remain available in the JSON response.
- Training data: 118 unique public notices from SUES Academic Affairs Office, 2022–2026.
- Evaluation: stratified 5-fold CV on pre-2025 notices and a 2025–2026 temporal holdout.
- Intended use: local routing and action planning support. It must not be used as the sole
  basis for degree, disciplinary, payment, or enrollment decisions.
- Known limits: small class imbalance, title drift, attachments not always extracted, and
  Chinese-only training. Low-confidence or incomplete inputs require human review.

## SMS spam model

- Task: English SMS ham/spam classification before action generation.
- Data: UCI SMS Spam Collection v.1, CC BY 4.0; exact duplicate messages removed.
- Representation: word 1–2 gram and character 3–5 gram TF-IDF features.
- Learned model: balanced logistic regression, `C=2`.
- Intended use: high-confidence blocking, not definitive fraud adjudication.
- Known limits: English-centric and trained on older SMS; does not cover Chinese phishing.
  Chinese security risks are handled conservatively by local sensitive-information rules and
  human verification.
