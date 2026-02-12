#!/bin/bash

# Build helper script to temporarily move utility files during builds
# This preserves VyOS's original testing methodology while allowing development

CONF_MODE_DIR="src/conf_mode"
TEMP_DIR="temp_configs"

# Files that don't follow VyOS config script pattern
UTILITY_FILES=(
    "apn_discovery.py"
    "connection_manager.py"
    "interfaces_wwan2.py"
    "interfaces_wwan_config.py"
    "interfaces_wwan_main.py"
    "interfaces_wwan_service_manager.py"
    "interfaces_wwan_state_machine.py"
    "interfaces_wwan_util.py"
    "refactoring_framework.py"
    "state_transition_manager.py"
    "wwan_utilities.py"
)

move_files_for_build() {
    echo "Moving utility files for clean build..."
    mkdir -p "$TEMP_DIR/utility_files"

    for file in "${UTILITY_FILES[@]}"; do
        if [ -f "$CONF_MODE_DIR/$file" ]; then
            mv "$CONF_MODE_DIR/$file" "$TEMP_DIR/utility_files/"
            echo "  Moved $file"
        fi
    done

    # Regenerate configd-include.json
    python3 scripts/generate-configd-include-json.py
    echo "Updated configd-include.json"
}

restore_files_after_build() {
    echo "Restoring utility files after build..."

    for file in "${UTILITY_FILES[@]}"; do
        if [ -f "$TEMP_DIR/utility_files/$file" ]; then
            mv "$TEMP_DIR/utility_files/$file" "$CONF_MODE_DIR/"
            echo "  Restored $file"
        fi
    done

    # Regenerate configd-include.json
    python3 scripts/generate-configd-include-json.py
    echo "Updated configd-include.json"
}

case "$1" in
    "prepare")
        move_files_for_build
        ;;
    "restore")
        restore_files_after_build
        ;;
    "test")
        move_files_for_build
        python3 -m pytest src/tests/test_configd_inspect.py -v
        restore_files_after_build
        ;;
    *)
        echo "Usage: $0 {prepare|restore|test}"
        echo "  prepare - Move utility files for clean build"
        echo "  restore - Restore utility files after build"
        echo "  test    - Run tests with clean environment"
        exit 1
        ;;
esac
