# Lyrics Slide Show

**Lyrics Slide Show** is an application built with Python and Django that allows you to easily manage the display of slides linked to songs. The display is not linear but follows the order of the song's verses and choruses.

## Features

- Manage song lyrics and slides
- Display slides in the order of verses and choruses
- User-friendly interface

## Installation

1. Clone the repository:
    ```bash
    git clone https://github.com/yourusername/lyrics-slide-show.git
    ```
2. Navigate to the project directory:
    ```bash
    cd lyrics-slide-show
    ```
3. Create a virtual environment:
    ```bash
    python3 -m venv env
    ```
4. Activate the virtual environment:
    - On Windows:
        ```bash
        .\env\Scripts\activate
        ```
    - On macOS and Linux:
        ```bash
        source env/bin/activate
        ```
5. Install the required dependencies:
    ```bash
    pip install -r requirements.txt
    ```
6. Apply migrations:
    ```bash
    python manage.py migrate
    ```
7. Run the development server:
    ```bash
    python manage.py runserver
    ```

## Usage

1. Open your web browser and go to `http://127.0.0.1:8000/`.
2. Add new songs and their corresponding slides.
3. Start the slide show and enjoy the synchronized display of lyrics.

## Contributing

Contributions are welcome! Please fork the repository and submit a pull request.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Contact

For any questions or suggestions, please contact [your-email@example.com](mailto:your-email@example.com).
