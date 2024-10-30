import os

print('§§§§§§§§§§§§§§§§§')
print('§§§ MODE PROD §§§')
print('§§§§§§§§§§§§§§§§§')

os.environ["DB_FUNCTIONAL_HOST"] = os.getenv('CARTHOGRAPHIE_FUNCTIONAL_HOST')
os.environ["DB_FUNCTIONAL_USER"] = os.getenv('CARTHOGRAPHIE_FUNCTIONAL_USER')
os.environ["DB_FUNCTIONAL_PASSWORD"] = os.getenv('CARTHOGRAPHIE_FUNCTIONAL_PASSWORD')
os.environ["DB_FUNCTIONAL_DATABASE"] = os.getenv('CARTHOGRAPHIE_FUNCTIONAL_DATABASE')
os.environ["DB_FUNCTIONAL_SSL"] = os.getenv('CARTHOGRAPHIE_FUNCTIONAL_SSL')

from .base import *
