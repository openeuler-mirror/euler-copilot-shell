"""PyInstaller 配置文件"""

import os
from pathlib import Path

# 项目根目录
project_root = Path(os.getcwd())
src_dir = project_root / "src"

# 隐藏导入
hidden_imports = [
    # Textual widgets 相关模块
    "textual.widgets._tab_pane",
    "textual.widgets._tabbed_content",
    "textual.widgets._button",
    "textual.widgets._input",
    "textual.widgets._label",
    "textual.widgets._progress_bar",
    "textual.widgets._rich_log",
    "textual.widgets._static",
    "textual.widgets._header",
    "textual.widgets._tree",
    "textual.widgets._data_table",
    "textual.widgets._option_list",
    "textual.widgets._footer",
    "textual.widgets._loading_indicator",
    "textual.widgets._text_area",
    "textual.widgets._markdown_viewer",
    "textual.widgets._select",
    "textual.widgets._checkbox",
    "textual.widgets._radio_button",
    "textual.widgets._sparkline",
    "textual.widgets._switch",
    "textual.widgets._tabs",
]

# 数据文件
added_files = [
    (str(src_dir / "app" / "css" / "styles.tcss"), "app/css"),
    # 国际化翻译文件
    (str(src_dir / "i18n" / "locales" / "en_US" / "LC_MESSAGES" / "messages.mo"), "i18n/locales/en_US/LC_MESSAGES"),
    (str(src_dir / "i18n" / "locales" / "zh_CN" / "LC_MESSAGES" / "messages.mo"), "i18n/locales/zh_CN/LC_MESSAGES"),
]

a = Analysis(
    [str(src_dir / "main.py")],
    pathex=[str(src_dir)],
    binaries=[],
    datas=added_files,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="witty-assistant",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
