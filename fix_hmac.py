#!/usr/bin/env python3
"""
Fix for py-clob-client HMAC signature bug
This script patches the hmac.py file in the installed py-clob-client package
to fix the "Unauthorized/Invalid api key" error.

Run this after installing py-clob-client if you encounter API authentication issues.
"""

import os
import sys
import re

def find_hmac_file():
    """Find the hmac.py file in the installed py-clob-client package"""
    import py_clob_client
    package_path = os.path.dirname(py_clob_client.__file__)
    hmac_path = os.path.join(package_path, 'headers', 'hmac.py')
    return hmac_path if os.path.exists(hmac_path) else None

def patch_hmac_file(hmac_path):
    """Apply the fix to hmac.py"""
    print(f"Found hmac.py at: {hmac_path}")

    # Read the file
    with open(hmac_path, 'r') as f:
        content = f.read()

    # Backup original
    backup_path = hmac_path + '.backup'
    if not os.path.exists(backup_path):
        with open(backup_path, 'w') as f:
            f.write(content)
        print(f"✓ Created backup at: {backup_path}")

    # Check if already patched
    if 'json.dumps(body, separators=' in content:
        print("✓ File is already patched!")
        return True

    # Add json import if not present
    if 'import json' not in content:
        # Find the first import statement and add json import
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if line.startswith('import ') or line.startswith('from '):
                lines.insert(i, 'import json')
                break
        content = '\n'.join(lines)
        print("✓ Added json import")

    # Fix the signature generation line
    old_pattern = r'message \+= str\(body\)\.replace\(["\']\'["\']\s*,\s*["\']"["\']\)'
    new_code = 'message += json.dumps(body, separators=(",", ":"))'

    if re.search(old_pattern, content):
        content = re.sub(old_pattern, new_code, content)
        print("✓ Fixed HMAC signature generation")
    else:
        print("⚠ Could not find the exact pattern to replace")
        print("  The file might already be fixed or have a different format")
        return False

    # Write the patched content
    with open(hmac_path, 'w') as f:
        f.write(content)

    print("✓ Successfully patched hmac.py!")
    return True

def main():
    print("=" * 60)
    print("py-clob-client HMAC Fix Script")
    print("=" * 60)

    try:
        hmac_path = find_hmac_file()
        if not hmac_path:
            print("✗ Could not find hmac.py in py-clob-client package")
            print("  Make sure py-clob-client is installed:")
            print("  pip install py-clob-client")
            sys.exit(1)

        success = patch_hmac_file(hmac_path)

        if success:
            print("\n" + "=" * 60)
            print("✓ Fix applied successfully!")
            print("  You can now run your bot")
            print("=" * 60)
        else:
            print("\n" + "=" * 60)
            print("⚠ Fix could not be applied automatically")
            print("  Please upgrade to py-clob-client >= 0.28.0:")
            print("  pip install --upgrade py-clob-client")
            print("=" * 60)

    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
