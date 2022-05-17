from setuptools import setup, find_packages

setup(name="py_yuwinzer_server",
      version="0.3.14",
      description="Yuwinzer Server",
      author="Sary Petrova",
      author_email="test_t@gmail.com",
      packages=find_packages(),
      install_requires=['PyQt5', 'sqlalchemy', 'pycryptodome', 'pycryptodomex'],
      scripts=['server/server_run']
      )
