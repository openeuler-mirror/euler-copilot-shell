#!/bin/bash

# Check if ~/rpmbuild directory exists; if not, run rpmdev-setuptree
if [ ! -d ~/rpmbuild ]; then
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

# Build the RPM package using rpmbuild
rpmbuild --define "dist .oe2403" -bb "$spec_file" --nodebuginfo
# rpmbuild --define "_tag .a$(date +%s)" --define "dist .oe2203sp3" -bb "$spec_file" --nodebuginfo
# rpmbuild --define "_tag .beta3" --define "dist .oe2203sp3" -bb "$spec_file" --nodebuginfo
# rpmbuild --define "dist .oe2203sp3" -bb "$spec_file" --nodebuginfo
