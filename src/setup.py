from distutils.core import setup
from Cython.Build import cythonize

setup(ext_modules=cythonize(["interact.py", "cmd_generate.py"]))


function commandline {
    stty sane && python3 /eulercopilot/eulercopilot.py $READLINE_LINE
    READLINE_LINE=
    stty erase ^H
}
bind -x '"\C-l":commandline'

