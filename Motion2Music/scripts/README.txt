# Motion2Music Prompt Model (from LMA + Beats)

This is a **practical baseline**:
- Uses your existing `*_lma.csv` windows + `*_beats.csv` beat times.
- Learns **genre** (supervised) from AIST++ filename labels (when present).
- Learns **style adjectives** (unsupervised) using KMeans clustering.
- Outputs a stable, generator-friendly prompt string.

## Train

```bash
python train_prompt_model.py --project "PATH/TO/Motion2Music" --out "PATH/TO/Motion2Music/models/prompt_model.joblib" --clusters 12
```

## Infer a prompt

```bash
python infer_prompt.py --model "PATH/TO/Motion2Music/models/prompt_model.joblib" --lma "..._lma.csv" --beats "..._beats.csv"
```

## Notes

This does **not** learn full music arrangement (instrumentation, key, chord progressions) because that information
is not present in motion+beat CSVs. If you want prompts that match the *exact* original song, you need **audio labels**
(genre/mood/instrument tags or audio embeddings) per sequence, then train motion -> audio-tag model.
