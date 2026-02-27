# Motion2Music (cleaned)

This repo is a *cleaned* version of your current Motion2Music files, with a stable folder layout and imports that work after you re-organize folders.

## Folder layout

- `src/motion2music/` – Python package (beats, BVH loading, ML helpers)
- `scripts/` – CLI scripts (they auto-add `src/` to `PYTHONPATH`, so you can run them from anywhere)
- `models/` – trained `.joblib` models
- `outputs/` – outputs (npy files, etc.)

## Quick setup (Windows)

```bat
cd Motion2Music_Clean
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Run the beat refiner on a BVH

```bat
python scripts\beat_refiner_apply.py --bvh "C:\path\to\clip.bvh" --model "models\beat_refiner.joblib" --v2 --thr 0.40
```

Outputs are saved next to the BVH by default:
- `.ml_prob.npy`
- `.ml_events.npy`
- `.rule_events.npy`
- `.hybrid_events.npy`

## Notes

- The original scripts expected modules like `ml_helpers.py` and `config.py` next to them. After re-organizing folders this breaks (especially on Linux). This version makes all imports go through the `motion2music` package.
- `JOINT_INDICES` is defined in `src/motion2music/config.py`. If you want to use a specific joint subset for beat extraction, update it there.
