# Copyright (c) Huawei Technologies Co., Ltd. 2024-2024. All rights reserved.

import os

from Cython.Build import cythonize
from Cython.Distutils import build_ext
from setuptools import setup
from setuptools.extension import Extension


def add_py_files(module_name):
    return [
        os.path.join(module_name, f)
        for f in os.listdir(module_name)
        if f.endswith('.py')
    ]


# 定义编译选项
cython_compile_options = {
    'language_level': '3',
    'annotate': False,  # 生成 HTML 注解文件
    'compiler_directives': {},
}

# 定义 Cython 编译规则
cython_files = []
cython_files += add_py_files('copilot/app')
cython_files += add_py_files('copilot/backends')
cython_files += add_py_files('copilot/utilities')

extensions = [Extension(f.replace("/", ".")[:-3], [f]) for f in cython_files]

# 定义 setup() 参数
setup(
    name='copilot',
    version='1.2',
    description='openEuler Copilot System CLI Tool',
    author='Hongyu Shi',
    author_email='shihongyu15@huawei.com',
    url='https://gitee.com/openeuler-customization/euler-copilot-shell',
    py_modules=['copilot.__init__', 'copilot.__main__'],
    ext_modules=cythonize(
        extensions,
        compiler_directives=cython_compile_options['compiler_directives'],
        annotate=cython_compile_options['annotate'],
        language_level=cython_compile_options['language_level']
    ),
    packages=['copilot'],
    cmdclass={'build_ext': build_ext},
    include_package_data=True,
    zip_safe=False,
    classifiers=[
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'License :: OSI Approved :: Mulan Permissive Software License, Version 2',  # 木兰许可证 v2
        'Operating System :: POSIX :: Linux',
        'Operating System :: MacOS :: MacOS X'
    ],
    python_requires='>=3.9',  # Python 版本要求为 3.9 及以上
    install_requires=[  # 添加项目依赖的库
        'websockets',
        'requests',
        'rich',
        'typer',
        'questionary'
    ],
    entry_points={
        'console_scripts': ['copilot=copilot.__main__:entry_point']
    }
)
