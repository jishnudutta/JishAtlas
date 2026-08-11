# -*- mode: python ; coding: utf-8 -*-
#
# JishAtlas PyInstaller spec.
#
# Important: llama_cpp loads its native DLLs (llama.dll, ggml*.dll, mtmd.dll)
# at runtime with ctypes from llama_cpp/lib/, so PyInstaller's static analysis
# cannot see them. We must collect the package binaries and data explicitly,
# otherwise the packaged exe crashes with "Failed to load the shared library".
# google.genai is a large package with many submodules, so we collect all of
# them as hidden imports.

from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_dynamic_libs,
    collect_submodules,
)


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=collect_dynamic_libs('llama_cpp'),
    datas=collect_data_files('llama_cpp'),
    hiddenimports=[
        'dotenv',
        'llama_cpp',
        'llama_cpp.llama_cpp',
        'llama_cpp.llama_chat_format',
        'llama_cpp.llama_grammar',
        'llama_cpp.llama_speculative',
        'llama_cpp.llama_tokenizer',
        'llama_cpp.llama_types',
        'llama_cpp.llava_cpp',
        'llama_cpp.mtmd_cpp',
        'google.genai',
        'google.genai.types',
        'huggingface_hub',
    ] + collect_submodules('google.genai'),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='JishAtlas',
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
    icon='assets/icon.ico',
    version='version_info.txt',
)
