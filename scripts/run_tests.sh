#!/usr/bin/env bash
set -euo pipefail

# In CI the action runs this script from inside the plugin directory.
# Tutor lives in the parent workspace's .tutor_venv — bring it into PATH.
if [ -f ../.tutor_venv/bin/activate ]; then
  source ../.tutor_venv/bin/activate
fi

echo "Running unit tests for openedx-corporate (partner_catalog)..."

tutor local exec lms bash -c "
  set -euo pipefail
  pip install pytest pytest-django pytest-cov pytest-mock --quiet
  cd /openedx/openedx-corporate
  pytest --ds=test_settings tests/ -v
"
