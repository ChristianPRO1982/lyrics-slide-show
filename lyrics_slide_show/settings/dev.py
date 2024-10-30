import os

print('§§§§§§§§§§§§§§§§')
print('§§§ MODE DEV §§§')
print('§§§§§§§§§§§§§§§§')

os.environ["DB_FUNCTIONAL_HOST"] = os.getenv('LOCAL_FUNCTIONAL_HOST')
os.environ["DB_FUNCTIONAL_USER"] = os.getenv('LOCAL_FUNCTIONAL_USER')
os.environ["DB_FUNCTIONAL_PASSWORD"] = os.getenv('LOCAL_FUNCTIONAL_PASSWORD')
os.environ["DB_FUNCTIONAL_DATABASE"] = os.getenv('LOCAL_FUNCTIONAL_DATABASE')
os.environ["DB_FUNCTIONAL_SSL"] = os.getenv('LOCAL_FUNCTIONAL_SSL')

from .base import *
