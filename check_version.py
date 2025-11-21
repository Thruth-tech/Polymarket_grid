#!/usr/bin/env python3
"""
Check py-clob-client version and HMAC implementation
"""

import sys
import os

print("=" * 60)
print("py-clob-client Version & HMAC Check")
print("=" * 60)

# Check version
try:
    import py_clob_client
    print(f"✓ py-clob-client is installed")

    # Try to get version
    if hasattr(py_clob_client, '__version__'):
        print(f"  Version: {py_clob_client.__version__}")
    else:
        print("  Version: Unable to determine")

    # Find package location
    package_path = os.path.dirname(py_clob_client.__file__)
    print(f"  Location: {package_path}")

    # Check for hmac.py
    hmac_path = os.path.join(package_path, 'headers', 'hmac.py')
    if os.path.exists(hmac_path):
        print(f"\n✓ Found hmac.py at: {hmac_path}")

        # Read and check content
        with open(hmac_path, 'r') as f:
            content = f.read()

        if 'json.dumps(body, separators=' in content:
            print("✓ HMAC file already has the fix!")
            print("  The bug should be resolved.")
        elif 'str(body).replace' in content:
            print("✗ HMAC file has the BUG!")
            print("  Need to apply the fix.")
        else:
            print("? HMAC implementation unclear")
            print("  File content doesn't match expected patterns")
    else:
        print(f"\n✗ hmac.py not found at expected location")
        print(f"  Looking for other possible locations...")

        # Try to find it
        import glob
        possible_paths = glob.glob(os.path.join(package_path, '**', 'hmac.py'), recursive=True)
        if possible_paths:
            print(f"  Found at: {possible_paths[0]}")
        else:
            print("  Could not find hmac.py anywhere in package")

    # Try a test import of the hmac module
    try:
        from py_clob_client.headers import hmac
        print("\n✓ Can import hmac module successfully")
    except ImportError as e:
        print(f"\n✗ Cannot import hmac module: {e}")

except ImportError:
    print("✗ py-clob-client is NOT installed")
    print("  Run: pip install py-clob-client")
    sys.exit(1)
except Exception as e:
    print(f"\n✗ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 60)
print("Next steps:")
print("  If bug is present: We need to manually patch it")
print("  If fix is present: Try running the bot with: python3 poly.py")
print("=" * 60)
