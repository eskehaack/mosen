import os
import random
import secrets


def property_rng():
    seed_text = os.environ.get("MOSEN_PROPERTY_SEED")
    seed = int(seed_text, 0) if seed_text else secrets.randbits(64)
    return seed, random.Random(seed)


def property_context(test_name, seed, scenario_index):
    return (
        f"{test_name} failed for seed={seed}, scenario={scenario_index}. "
        f'Reproduce with: $env:MOSEN_PROPERTY_SEED="{seed}"; '
        f".\\.venv\\Scripts\\python.exe -m pytest"
    )
