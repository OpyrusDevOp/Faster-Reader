import PyInstaller.__main__
import os
import shutil

def build():
    print("Building Faster Reader...")

    # Clean previous builds
    if os.path.exists("build"):
        shutil.rmtree("build")
    if os.path.exists("dist"):
        shutil.rmtree("dist")

    PyInstaller.__main__.run([
        'app.py',
        '--name=FasterReader',
        '--windowed',  # Don't show console window
        '--onefile',   # Bundle everything into a single executable
        '--clean',
        # Add necessary hidden imports if PyInstaller misses them
        '--hidden-import=PySide6',
        '--hidden-import=edge_tts',
        '--hidden-import=emoji',
        # Exclude modules we don't need
        '--exclude-module=tkinter',
        '--exclude-module=matplotlib',
        '--exclude-module=notebook',
        '--exclude-module=scipy',
        '--exclude-module=pandas',
        '--exclude-module=numpy', # Unless used by dependencies, but usually heavy
    ])

    print("Build complete. Executable is in the 'dist' folder.")

if __name__ == "__main__":
    build()
