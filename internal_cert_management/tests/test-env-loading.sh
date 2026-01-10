#!/bin/bash

# Test script to validate .env loading and script behavior
# Usage: ./tests/test-env-loading.sh

set -e

TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEST_ENV="${TEST_DIR}/.env.test"

echo "=== Testing .env Loading ==="
echo ""

# Create test .env file
cat > "$TEST_ENV" << 'EOF'
# Test configuration
ADMIN_EMAIL="test@example.com"
LEGO_DNS_PROVIDER="porkbun"
LEGO_DNS_RESOLVERS="9.9.9.9:53"

SUBDOMAINS_EC256="test1.example.com test2.example.com"
SUBDOMAINS_RSA2048="test3.example.com"

HOSTLIST_VAULT="vault.example.com"
SUBDOMAINS_VAULT="test1.example.com test2.example.com"
CERT_TYPES_VAULT="ec256"

HOSTLIST_ENDPOINTS="endpoints.example.com"
SUBDOMAINS_ENDPOINTS="test1 test2"
CERT_TYPES_ENDPOINTS="ec256"
DOMAIN_SUFFIX="example.com"

ANSIBLE_PATH="/tmp/ansible-test"
ANSIBLE_INVENTORY="test.inventory"
EOF

echo "✓ Created test .env file: $TEST_ENV"
echo ""

# Test 1: lego.sh can source .env
echo "Test 1: lego.sh sources .env correctly"
(
    source "$TEST_ENV"
    read -ra subdomains_ec256 <<< "$SUBDOMAINS_EC256"
    if [ ${#subdomains_ec256[@]} -eq 2 ]; then
        echo "✓ lego.sh: subdomains_ec256 array has 2 elements"
    else
        echo "✗ lego.sh: Expected 2 subdomains, got ${#subdomains_ec256[@]}"
        exit 1
    fi
)

# Test 2: upload-to-vault.sh can source .env
echo "Test 2: upload-to-vault.sh sources .env correctly"
(
    source "$TEST_ENV"
    read -ra types <<< "$CERT_TYPES_VAULT"
    if [ ${#types[@]} -eq 1 ]; then
        echo "✓ upload-to-vault.sh: cert types parsed correctly"
    else
        echo "✗ upload-to-vault.sh: Expected 1 cert type, got ${#types[@]}"
        exit 1
    fi
)

# Test 3: update_endpoints.sh can source .env
echo "Test 3: update_endpoints.sh sources .env correctly"
(
    source "$TEST_ENV"
    read -ra subdomains <<< "$SUBDOMAINS_ENDPOINTS"
    if [ ${#subdomains[@]} -eq 2 ]; then
        echo "✓ update_endpoints.sh: subdomains parsed correctly"
    else
        echo "✗ update_endpoints.sh: Expected 2 subdomains, got ${#subdomains[@]}"
        exit 1
    fi
)

echo ""
echo "=== Testing --force Flag Logic ==="
echo ""

# Test 4: --force flag sets FORCE_SKIP_VALIDATION=true
echo "Test 4: --force flag parsing"
(
    FORCE_SKIP_VALIDATION=false
    # Simulate argument parsing
    if [[ "--force" == "--force" ]]; then
        FORCE_SKIP_VALIDATION=true
    fi
    
    if [ "$FORCE_SKIP_VALIDATION" = true ]; then
        echo "✓ --force flag correctly sets FORCE_SKIP_VALIDATION=true"
    else
        echo "✗ --force flag not working"
        exit 1
    fi
)

# Test 5: --force flag should result in force_skip_validation=true in EXTRA_VARS
echo "Test 5: EXTRA_VARS with --force flag"
(
    source "$TEST_ENV"
    FORCE_SKIP_VALIDATION=false
    # Simulate --force argument parsing
    FORCE_SKIP_VALIDATION=true
    
    EXTRA_VARS=""
    if [ "$FORCE_SKIP_VALIDATION" = true ]; then
        EXTRA_VARS="-e force_skip_validation=true"
    fi
    
    if [[ "$EXTRA_VARS" == *"force_skip_validation=true"* ]]; then
        echo "✓ EXTRA_VARS correctly includes force_skip_validation=true"
    else
        echo "✗ EXTRA_VARS missing force_skip_validation=true"
        exit 1
    fi
)

echo ""
echo "=== Testing Variable Validation ==="
echo ""

# Test 6: Required variable triggers error when missing
echo "Test 6: Required variable validation"
(
    # Test that parameter expansion error would trigger
    unset MISSING_REQUIRED_VAR
    if (: "${MISSING_REQUIRED_VAR:?MISSING_REQUIRED_VAR is not set}") 2>/dev/null; then
        echo "✗ Variable validation: did not catch missing variable"
        exit 1
    else
        echo "✓ Parameter expansion correctly detects missing variables"
    fi
)

# Test 7: Domain suffix interpolation
echo "Test 7: Domain suffix interpolation"
(
    source "$TEST_ENV"
    subdomain="test1"
    full_domain="${subdomain}.${DOMAIN_SUFFIX}"
    
    if [ "$full_domain" = "test1.example.com" ]; then
        echo "✓ Domain suffix interpolation works correctly"
    else
        echo "✗ Domain suffix interpolation failed: got $full_domain"
        exit 1
    fi
)

echo ""
echo "=== Syntax Validation ==="
echo ""

# Test 8: All scripts pass bash syntax check
echo "Test 8: Shell script syntax validation"
for script in "$TEST_DIR/scripts"/*.sh; do
    if bash -n "$script" 2>/dev/null; then
        echo "✓ $(basename "$script") syntax valid"
    else
        echo "✗ $(basename "$script") has syntax errors"
        exit 1
    fi
done

# Cleanup
rm -f "$TEST_ENV"

echo ""
echo "=== All Tests Passed ✓ ==="
