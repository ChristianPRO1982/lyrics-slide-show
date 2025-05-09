# Lyrics Slide Show

[![Latest Release](https://img.shields.io/github/release/ChristianPRO1982/lyrics-slide-show.svg)](https://github.com/ChristianPRO1982/lyrics-slide-show/releases/latest)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)

![Django](https://img.shields.io/badge/Django-5.1.6-green?logo=django&logoColor=white)
![Django](https://img.shields.io/badge/Django-Framework-green?logo=django)

[![License](https://img.shields.io/github/license/ChristianPRO1982/lyrics-slide-show.svg)](https://github.com/ChristianPRO1982/lyrics-slide-show/blob/main/LICENSE)

“Lyrics Slide Show” is an application that lets you easily manage the display of slides linked to songs. The display is not linear, but follows the order of the song's verses and choruses.

## Features

- Manage song lyrics and slides
- Non-linear slide display
- Easy to use interface

## .ENV

```bash
DEBUG=1
SQL_REQUEST_LOG=1 # 0: no log, 1: SQL name, 2: SQL name and request
SQL_REQUEST_LOG_NAME_PREFIX='[DEV]'
LOG_RETENTION_DAYS=1

###########
# SECRETS #
###########
SECRET_KEY=''

#######
# BDD #
#######
LOCAL_FUNCTIONAL_HOST='localhost'
LOCAL_FUNCTIONAL_USER='root'
LOCAL_FUNCTIONAL_PASSWORD=''
LOCAL_FUNCTIONAL_DATABASE=''
LOCAL_FUNCTIONAL_SSL=''

CARTHOGRAPHIE_FUNCTIONAL_HOST=''
CARTHOGRAPHIE_FUNCTIONAL_USER=''
CARTHOGRAPHIE_FUNCTIONAL_PASSWORD=''
CARTHOGRAPHIE_FUNCTIONAL_DATABASE=''
CARTHOGRAPHIE_FUNCTIONAL_SSL=''
```

## Installation

1. Clone the repository:
    ```bash
    git clone https://github.com/yourusername/lyrics-slide-show.git
    ```
2. Navigate to the project directory:
    ```bash
    cd lyrics-slide-show
    ```
3. Install the dependencies:
    ```bash
    pip install -r requirements.txt
    ```
4. Apply migrations:
    ```bash
    python manage.py migrate
    ```
5. Run the development server:
    ```bash
    python manage.py runserver
    ```

## Usage

1. Open your web browser and go to `http://127.0.0.1:8000/`.
2. Add and manage your songs and slides through the web interface.
3. Enjoy your non-linear lyrics slide show!

## Contributing

Contributions are welcome! Please fork the repository and submit a pull request.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Contact

For any inquiries, please contact [Christian from cARThographie](mailto:carthographie@outlook.fr).

# Memo

## commands for translations

### messages extraction

```bash
django-admin makemessages -l fr
django-admin makemessages -l en
```

### compile messages

```bash
django-admin compilemessages
```

## django

```bash
python manage.py runserver
python manage.py collectstatic
python manage.py makemigrations
python manage.py migrate
```

## MySQL
```sql
mysqldump -u root -p --no-data carthographie > schema.sql
```