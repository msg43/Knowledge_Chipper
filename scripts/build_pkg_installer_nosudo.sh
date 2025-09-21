#!/bin/bash
# build_pkg_installer_nosudo.sh - Build PKG without requiring sudo
# This version doesn't set root ownership during build, relying on pkgbuild to handle it

# This is a symlink to the main build script with an environment variable set
export NO_SUDO_BUILD=1
exec "$(dirname "${BASH_SOURCE[0]}")/build_pkg_installer.sh" "$@"
