#!/usr/bin/env python3
#
# Copyright 2026 Perle Systems Limited

import os
import argparse
from pathlib import Path
from shutil import copy, copytree, rmtree

from vyos.system import grub
from vyos.system import image
from vyos.template import render


# -------------------------------
# Constants
# -------------------------------
DEFAULT_BOOT_VARS: dict[str, str] = {
    'timeout': '0',
    'console_type': 'tty',
    'console_num': '0',
    'console_speed': '115200',
    'bootmode': 'normal'
}

TARGET_P2 = "/mnt/p3"
ROOTFS = "/"
ISO = "/mnt/iso"

SRC_DTB = f"{ISO}/boot/dtb"
LIVE = f"{ISO}/live"
BOOT = f"{TARGET_P2}/boot"
DST_DTB = f"{TARGET_P2}/boot/dtb"


# -------------------------------
# Utility Functions
# -------------------------------
def log(msg: str):
    print(f"[INFO] {msg}")


def safe_rmtree(path: Path):
    if path.exists():
        log(f"Removing {path}")
        rmtree(path, ignore_errors=True)


# -------------------------------
# GRUB Setup
# -------------------------------
def setup_grub(root_dir: str) -> None:
    log('Installing GRUB configuration files')

    grub_cfg_main = f'{root_dir}/{grub.GRUB_DIR_MAIN}/grub.cfg'
    grub_cfg_vars = f'{root_dir}/{grub.CFG_VYOS_VARS}'
    grub_cfg_modules = f'{root_dir}/{grub.CFG_VYOS_MODULES}'
    grub_cfg_menu = f'{root_dir}/{grub.CFG_VYOS_MENU}'

    render(grub_cfg_main, grub.TMPL_GRUB_MAIN, {})
    grub.common_write(root_dir)
    grub.vars_write(grub_cfg_vars, DEFAULT_BOOT_VARS)
    grub.modules_write(grub_cfg_modules, [])
    grub.write_cfg_ver(1, root_dir)
    render(grub_cfg_menu, grub.TMPL_GRUB_MENU, {})


# -------------------------------
# Image Copy Logic
# -------------------------------
def copy_image(version: str, dest: str):
    version_dir = Path(f"{BOOT}/{version}")
    os.makedirs(version_dir, exist_ok=True)

    log(f"Copying image for version: {version}")

    copytree(f"{ROOTFS}boot/",
             f"{BOOT}/{version}/",
             dirs_exist_ok=True,
             symlinks=True)

    # prune unwanted dirs
    safe_rmtree(Path(f'{BOOT}/{version}/dtb'))
    safe_rmtree(Path(f'{BOOT}/{version}/grub'))

    copy(f'{LIVE}/filesystem.squashfs',
         f'{BOOT}/{version}/{version}.squashfs')


def setup_default_firmware():
    default_name = "default-firmware"
    dest = Path(f"{BOOT}/{default_name}")

    safe_rmtree(dest)

    log("Creating default firmware image")

    copytree(f"{ROOTFS}boot/",
             f"{BOOT}/{default_name}/",
             dirs_exist_ok=True,
             symlinks=True)

    safe_rmtree(Path(f'{BOOT}/{default_name}/dtb'))
    safe_rmtree(Path(f'{BOOT}/{default_name}/grub'))

    copy(f'{LIVE}/filesystem.squashfs',
         f'{BOOT}/{default_name}/{default_name}.squashfs')

    return default_name


# -------------------------------
# Main Execution
# -------------------------------
def main():
    parser = argparse.ArgumentParser(description="VyOS installer runner")
    parser.add_argument(
        "--grub-target",
        required=True,
        help="Block device to install GRUB onto (e.g. /dev/loop0)"
    )
    args = parser.parse_args()

    grub_target = args.grub_target
    log(f"Using GRUB target device: {grub_target}")

    version = image.get_image_version(ROOTFS)
    log(f"Detected running version: {version}")

    # persistence config
    Path(f'{TARGET_P2}/persistence.conf').write_text('/ union\n')

    # copy DTBs
    log("Copying DTB files")
    copytree(f"{SRC_DTB}/ti",
             f"{DST_DTB}/ti",
             dirs_exist_ok=True)

    # copy main image
    copy_image(version, BOOT)

    # GRUB setup
    setup_grub(TARGET_P2)
    grub.create_structure()
    grub.version_add(version, TARGET_P2)
    grub.set_current_default(version, TARGET_P2)
    grub.set_console_type('ttyS', TARGET_P2)

    # default firmware
    default_name = setup_default_firmware()
    grub.version_add(default_name, TARGET_P2)
    grub.set_factory_default(default_name, TARGET_P2)

    # install GRUB
    log("Installing GRUB to disk")
    grub.install(grub_target, f'{BOOT}/', f'{BOOT}/efi')

    # sort inodes
    grub.sort_inodes(f'{TARGET_P2}/{grub.GRUB_DIR_VYOS}')
    grub.sort_inodes(f'{TARGET_P2}/{grub.GRUB_DIR_VYOS_VERS}')

    log("IGOS production image completed successfully.")


# -------------------------------
# Entry Point
# -------------------------------
if __name__ == "__main__":
    main()

