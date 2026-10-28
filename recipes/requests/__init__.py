"""Local requests recipe (pure Python).

The p4a master kivy recipe lists `requests` in python_depends, which would
cause p4a to pip-install requests (and its transitive deps like
charset-normalizer) into the broken android venv. On Python 3.14 that fails
with "wheel is not a supported wheel on this platform" because p4a master's
run_pymodules_install does not pass --platform/--python-version.

We instead build requests from source (2.25.1, before the urllib3 upgrade
that pulled in charset-normalizer) so it is installed as a real recipe. The
kivy shadow recipe below drops requests from python_depends, and requests
2.25.1's runtime deps (urllib3, chardet, idna, certifi) are still provided
by kivy's python_depends.
"""

from pythonforandroid.recipe import PythonRecipe


class RequestsRecipe(PythonRecipe):
    version = '2.25.1'
    url = 'https://files.pythonhosted.org/packages/source/r/requests/requests-{version}.tar.gz'
    name = 'requests'
    depends = ['setuptools']
    site_packages_name = 'requests'
    call_hostpython_via_targetpython = False


recipe = RequestsRecipe()
