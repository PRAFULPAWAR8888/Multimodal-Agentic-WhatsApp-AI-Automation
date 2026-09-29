import os
import glob
from setuptools import setup
from Cython.Build import cythonize

# NOTE: This script compiles the critical core components of the application into 
# binary extensions (.pyd on Windows, .so on Linux) to prevent tampering and resale.

def build_extensions():
    print("Compiling core modules into secure Cython extensions...")
    
    # Define the sensitive files to compile. 
    # Do NOT compile entry points like main.py, as ASGI/Uvicorn needs normal modules.
    sensitive_files = [
        "src/whatsapp_agent/core/license.py",
        "src/whatsapp_agent/config/settings.py",
        "src/whatsapp_agent/agents/state.py",
        "src/whatsapp_agent/workflows/main_workflow.py"
    ]
    
    # Filter out files that don't exist
    files_to_compile = [f for f in sensitive_files if os.path.exists(f)]
    
    if not files_to_compile:
        print("No sensitive files found to compile.")
        return

    # Run cythonize
    setup(
        ext_modules = cythonize(
            files_to_compile,
            compiler_directives={'language_level': "3"}
        )
    )
    
    print("Compilation complete. You can now delete the original .py files for these modules before shipping.")

if __name__ == "__main__":
    build_extensions()
