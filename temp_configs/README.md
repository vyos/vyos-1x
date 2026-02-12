# VyOS Build Workaround

This directory contains a temporary workaround for building vyos-1x while development files are being finalized.

## Files:
- `my_config.conf` - Temporary configuration file (will be replaced with proper config from coworker)
- `utility_files/` - Utility Python files that don't follow VyOS config script patterns

## Usage:

### For running tests:
```bash
./build-helper.sh test
```

### For preparing a clean build:
```bash
./build-helper.sh prepare
# Run your build process here
./build-helper.sh restore
```

### Manual operations:
```bash
# Move utility files out before build
./build-helper.sh prepare

# Restore utility files after build
./build-helper.sh restore
```

## What it does:
- Temporarily moves utility files out of `src/conf_mode` during builds
- Regenerates `data/configd-include.json` to only include proper VyOS config scripts
- Runs tests in clean environment that passes VyOS standards
- Restores all files after build/test completion

## When to remove:
Once proper configuration files are received from coworker, move `my_config.conf` to its proper location and remove this workaround system.
