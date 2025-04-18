import os

print('§§§§§§§§§§§§§§§§§')
print('§§§ MODE PROD §§§')
print('§§§§§§§§§§§§§§§§§')

os.environ["DB_FUNCTIONAL_HOST"] = os.getenv('DOCKER_MYSQL_HOST')
os.environ["DB_FUNCTIONAL_USER"] = os.getenv('DOCKER_MYSQL_USER')
os.environ["DB_FUNCTIONAL_PASSWORD"] = os.getenv('DOCKER_MYSQL_PASSWORD')
os.environ["DB_FUNCTIONAL_DATABASE"] = os.getenv('DOCKER_MYSQL_DATABASE')
os.environ["DB_FUNCTIONAL_SSL"] = os.getenv('DOCKER_MYSQL_SSL')

from .base import *
