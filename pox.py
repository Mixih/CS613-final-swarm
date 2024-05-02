#!/bin/python3

import sys
import os.path

from pox.boot import boot

# add internal pox controller module dir to path and boot pox
if __name__ == "__main__":
    base = sys.path[0]
    sys.path.insert(0, os.path.abspath(os.path.join(base, "swarmsdn", "controller")))
    boot()
