#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script for ExcelChartExporter

Usage:
    python test_excel_export.py <data_file> <output.xlsx>

Example:
    python test_excel_export.py Samples/sample_data.csv pyADR_Export_test.xlsx
"""

import sys
import os
import numpy as np
from ExcelChartExporter import export_diagrams_to_excel

def test_excel_export(data_file, output_file='pyADR_Export_test.xlsx'):
    """Test Excel export functionality."""

    print(f"[Test] Input file: {data_file}")
    print(f"[Test] Output file: {output_file}")

    # Check if input file exists
    if not os.path.exists(data_file):
        print(f"[Error] Data file not found: {data_file}")
        return False

    # Create dummy mask (all 1s = include all)
    with open(data_file, 'r', encoding='utf-8-sig', errors='ignore') as f:
        nrows = len(f.readlines()) - 1
    mask = np.ones(nrows)

    # Dummy constants (not used for export, but required)
    constants = np.ones(20)

    # Export
    try:
        result = export_diagrams_to_excel(
            data_file,
            mask,
            constants,
            output_file,
            diagrams=['DFN', 'DFI', 'DFW', 'DFA']
        )
        print(f"[Test] ✓ Export successful: {result}")
        return True
    except Exception as e:
        print(f"[Test] ✗ Export failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python test_excel_export.py <data_file> [output.xlsx]")
        print("\nExample:")
        print("  python test_excel_export.py Samples/sample_data.csv pyADR_Export.xlsx")
        sys.exit(1)

    data_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else 'pyADR_Export_test.xlsx'

    success = test_excel_export(data_file, output_file)
    sys.exit(0 if success else 1)
