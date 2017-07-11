"""
Cross-version Python tool for listing script dependencies

Usage: pythonX.X list-dependencies.py <script.py> <search paths>...
  If search paths not given, sys.path is used (see modulefinder.ModuelFinder)

Output: New-line seperated list of python source files
"""

import sys
import modulefinder

def main():
    script = sys.argv[1]
    path = sys.argv[2:] or None # if not given use default

    finder = modulefinder.ModuleFinder(path=path or sys.path)
    finder.run_script(script)

    for module in finder.modules.values():
        if module.__file__ and module.__file__[-3:].lower() == '.py':
            print(module.__file__)

if __name__ == '__main__':
    main()
