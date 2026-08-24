# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_all, copy_metadata


streamlit_datas, streamlit_binaries, streamlit_hiddenimports = collect_all("streamlit")

local_modules = [
    "rsm_3d",
    "rsm_3d_obj",
    "rsm_config",
    "rsm_core",
    "rsm_dashboard",
    "rsm_design",
    "rsm_design_ui",
    "rsm_export",
    "rsm_plots",
    "rsm_result_ui",
    "rsm_state",
    "rsm_statistics",
    "rsm_table_component",
]

datas = streamlit_datas + [
    ("rsm_streamlit_app.py", "."),
    ("assets/rsm_icon.png", "assets"),
] + copy_metadata("streamlit") + copy_metadata("pywebview")

hiddenimports = streamlit_hiddenimports + local_modules + [
    "openpyxl",
    "openpyxl.cell._writer",
    "webview.platforms.win32",
    "webview.platforms.winforms",
    "webview.platforms.edgechromium",
]

a = Analysis(
    ["rsm_desktop_launcher.py"],
    pathex=["."],
    binaries=streamlit_binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "matplotlib",
        "plotly.matplotlylib",
        "webview.platforms.android",
        "webview.platforms.cef",
        "webview.platforms.cocoa",
        "webview.platforms.gtk",
        "webview.platforms.qt",
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="DOE_RSM",
    icon="assets/rsm_icon.ico",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="DOE_RSM",
)
