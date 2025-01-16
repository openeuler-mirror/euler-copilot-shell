#!/bin/bash

# Check if ~/rpmbuild directory exists; if not, run rpmdev-setuptree
if [ ! -d ~/rpmbuild ]; then
    if ! command -v rpmdev-setuptree &> /dev/null; then
        echo "Command \"rpmdevtools\" not found: dnf install rpmdevtools"
        exit 1
    fi
    rpmdev-setuptree
fi

# Run the Python script
python3 create_tarball.py

# Find the generated tarball file and move it to ~/rpmbuild/SOURCES
generated_tarball=$(find . -maxdepth 1 -type f -name "*.tar.gz" -printf "%f\n")
mv "./$generated_tarball" ~/rpmbuild/SOURCES/

# Locate the spec file in the parent directory
spec_file="eulercopilot-cli.spec"

if [[ ! -f "$spec_file" ]]; then
    echo "Error: Could not find the spec file ($spec_file) in the parent directory."
    exit 1
fi

# Remove old builds
rm -f ~/rpmbuild/RPMS/"$(uname -m)"/eulercopilot-cli-*

# Read command-line arguments
use_release=false
while [[ $# -gt 0 ]]; do
    case $1 in
        -t|--tag)
            custom_tag="$2"
            shift 2
            ;;
        -r|--release)
            use_release=true
            shift
            ;;
        *)
            shift
            ;;
    esac
done

# Get dist tag
dist=$(python3 -c '
import re
with open("/etc/openEuler-release", "r") as f:
    release = f.readline().strip()
version = re.search(r"(\d+\.\d+)", release).group(1)
major, minor = version.split(".")
sp = re.search(r"SP(\d+)", release)
sp_str = f"sp{sp.group(1)}" if sp else ""
print(f"oe{major}{minor}{sp_str}")
')

# Prepare `rpmbuild` command
if [ "$use_release" = true ]; then
    rpmbuild_cmd="rpmbuild --define \"dist .${dist}\" -bb \"$spec_file\" --nodebuginfo"
else
    tag=${custom_tag:-"a$(date +%s)"}
    rpmbuild_cmd="rpmbuild --define \"_tag .${tag}\" --define \"dist .${dist}\" -bb \"$spec_file\" --nodebuginfo"
fi

# Build the RPM package using rpmbuild
eval "$rpmbuild_cmd"
