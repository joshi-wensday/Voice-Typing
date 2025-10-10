# Manual Tests

This directory contains scripts for manual testing and feature exploration.

These are not automated tests - they are interactive scripts for visual testing and demonstration.

## Files

### UI Testing
- `test_ui_modernization.py` - Interactive test for modern UI features
  - Tests circular visualizer animations
  - Tests glassmorphism settings window
  - Tests custom widgets (buttons, sliders, dropdowns, color pickers)
  - Useful for visual regression testing

### Feature Testing  
- `test_new_features.py` - Test script for new feature validation
  - Manual validation of recent features
  - Quick smoke testing

## Running Manual Tests

```bash
# Activate virtual environment
venv\Scripts\activate

# Run UI modernization test
python tests/manual/test_ui_modernization.py

# Run new features test
python tests/manual/test_new_features.py
```

## Automated Tests

For automated unit and integration tests, see:
- [Unit Tests](../unit/)
- [Integration Tests](../integration/)

