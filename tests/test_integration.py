#!/usr/bin/env python3
"""Integration Tests - Test the complete registration flow."""
import json
import os
import sys
import tempfile
import shutil
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import validate as v


def test_validate_name():
    """Test subdomain name validation."""
    print("Testing name validation...")
    
    # Valid names
    assert v.validate_name("mysite") == [], "Simple name should be valid"
    assert v.validate_name("my-site") == [], "Name with hyphen should be valid"
    assert v.validate_name("s1.mysite") == [], "Two levels should be valid"
    assert v.validate_name("s1.nextcloud.yoann") == [], "Three levels should be valid"
    
    # Invalid names
    assert len(v.validate_name("")) > 0, "Empty name should be invalid"
    assert len(v.validate_name("BLOG")) > 0, "Uppercase should be invalid"
    assert len(v.validate_name("my blog")) > 0, "Space should be invalid"
    assert len(v.validate_name("nextcloud")) > 0, "Reserved name should be invalid"
    assert len(v.validate_name("yoann.nextcloud")) > 0, "Should not end with reserved"
    
    # Valid with reserved word not at end
    assert v.validate_name("nextcloud.yoann") == [], "Reserved word not at end should be valid"
    
    print("  ✅ Name validation tests passed")


def test_validate_config():
    """Test configuration validation."""
    print("Testing config validation...")
    
    # Valid config
    valid_config = json.dumps({
        "owner": {"github": "testuser", "github_id": 123456},
        "records": [{"type": "CNAME", "value": "testuser.github.io"}]
    })
    errors, warnings = v.validate_config("test", valid_config)
    assert errors == [], f"Valid config should have no errors: {errors}"
    
    # Invalid config - missing owner
    invalid_config = json.dumps({
        "records": [{"type": "CNAME", "value": "testuser.github.io"}]
    })
    errors, warnings = v.validate_config("test", invalid_config)
    assert len(errors) > 0, "Missing owner should have errors"
    
    # Invalid config - bad record type
    bad_record_config = json.dumps({
        "owner": {"github": "testuser", "github_id": 123456},
        "records": [{"type": "INVALID", "value": "test"}]
    })
    errors, warnings = v.validate_config("test", bad_record_config)
    assert len(errors) > 0, "Invalid record type should have errors"
    
    # Invalid config - bad CNAME
    bad_cname_config = json.dumps({
        "owner": {"github": "testuser", "github_id": 123456},
        "records": [{"type": "CNAME", "value": "invalid..hostname"}]
    })
    errors, warnings = v.validate_config("test", bad_cname_config)
    assert len(errors) > 0, "Invalid CNAME should have errors"
    
    print("  ✅ Config validation tests passed")


def test_parse_form():
    """Test form parsing."""
    print("Testing form parsing...")
    
    # Import process_issue module
    import process_issue as pi
    
    # Test form body
    form_body = """### What do you want to do?
Register a new subdomain

### Base domain
oxyd.space

### Subdomain name
blog

### Record type
CNAME

### Record value
testuser.github.io

### Enable www prefix
- [x] Yes, also create www.<subdomain>

### Terms
- [x] I will not use this subdomain for phishing, malware, spam or illegal content
- [x] I understand the service is provided as-is and may be discontinued"""
    
    sections = pi.parse_form(form_body)
    
    assert sections.get("What do you want to do?") == "Register a new subdomain"
    assert sections.get("Base domain") == "oxyd.space"
    assert sections.get("Subdomain name") == "blog"
    assert sections.get("Record type") == "CNAME"
    assert sections.get("Record value") == "testuser.github.io"
    
    print("  ✅ Form parsing tests passed")


def test_iter_config_paths():
    """Test iterating over config paths."""
    print("Testing config path iteration...")
    
    # Create test structure
    test_dir = Path("domains_test")
    test_zone = test_dir / "test.zone"
    test_zone.mkdir(parents=True, exist_ok=True)
    
    # Create test config
    test_config = test_zone / "blog.json"
    test_config.write_text(json.dumps({
        "owner": {"github": "testuser", "github_id": 123456},
        "records": [{"type": "CNAME", "value": "testuser.github.io"}]
    }))
    
    # Test iteration (we need to temporarily modify DOMAINS_DIR)
    original_domains_dir = v.DOMAINS_DIR
    v.DOMAINS_DIR = str(test_dir)
    
    try:
        configs = list(v.iter_config_paths())
        assert len(configs) == 1, f"Should find 1 config, found {len(configs)}"
        assert configs[0][0] == "test.zone", f"Zone should be test.zone, got {configs[0][0]}"
        assert configs[0][1] == "blog", f"Stem should be blog, got {configs[0][1]}"
    finally:
        v.DOMAINS_DIR = original_domains_dir
        shutil.rmtree(test_dir)
    
    print("  ✅ Config path iteration tests passed")


def main():
    """Run all tests."""
    print(" Running integration tests...\n")
    
    try:
        test_validate_name()
        test_validate_config()
        test_parse_form()
        test_iter_config_paths()
        
        print(f"\n{'=' * 50}")
        print("All tests passed! ✅")
        return 0
    
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
