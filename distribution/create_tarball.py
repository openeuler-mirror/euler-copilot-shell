import os
import re
import shutil
import tarfile


def extract_spec_fields(spec_file):
    with open(spec_file, "r", encoding="utf-8") as f:
        content = f.read()

    name_pattern = re.compile(r"^Name:\s*(.+)$", re.MULTILINE)
    version_pattern = re.compile(r"^Version:\s*(.+)$", re.MULTILINE)

    name_match = name_pattern.search(content)
    version_match = version_pattern.search(content)

    if name_match and version_match:
        return {"name": name_match.group(1).strip(), "version": version_match.group(1).strip()}
    else:
        raise ValueError("Could not find Name or Version fields in the spec file")


def create_cache_folder(spec_info, src_dir):
    name = spec_info["name"]
    version = spec_info["version"]

    cache_folder_name = f"{name}-{version}"
    cache_folder_path = os.path.join(os.path.dirname(src_dir), cache_folder_name)

    if not os.path.exists(cache_folder_path):
        os.makedirs(cache_folder_path)

    copy_files(src_dir, cache_folder_path)
    create_tarball(cache_folder_path, f"{cache_folder_name}.tar.gz")
    delete_cache_folder(cache_folder_path)


def copy_files(src_dir, dst_dir):
    for dirpath, _, files in os.walk(src_dir):
        relative_path = os.path.relpath(dirpath, src_dir)
        target_path = os.path.join(dst_dir, relative_path.strip(f"{os.curdir}{os.sep}"))

        if not os.path.exists(target_path):
            os.makedirs(target_path)

        for file in files:
            if file.endswith(".py") or file.endswith(".sh"):
                src_file = os.path.join(dirpath, file)
                dst_file = os.path.join(target_path, file)
                os.link(src_file, dst_file)  # 使用硬链接以节省空间和时间


def create_tarball(folder_path, tarball_name):
    with tarfile.open(tarball_name, "w:gz") as tar:
        tar.add(folder_path, arcname=os.path.basename(folder_path))


def delete_cache_folder(folder_path):
    shutil.rmtree(folder_path)


if __name__ == "__main__":
    SPEC_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "eulercopilot-cli.spec"))
    SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))

    info = extract_spec_fields(SPEC_FILE)
    create_cache_folder(info, SRC_DIR)
