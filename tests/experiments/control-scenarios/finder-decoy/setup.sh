set -eu
/opt/homebrew/bin/python3 "$HOME/code/machine-control/tests/experiments/control-scenarios/finder-decoy/fixture.py" setup \
  --root "$HOME/experiment/heldout-finder" --seed "${MC_EXPERIMENT_SEED:?}"
