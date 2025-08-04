# Football Web Manager

This is a web-based football management simulation game built with Python and Flask. The project features user registration and login backed by a SQLite database.

## Technologies Used
* **Backend:** Python
* **Web Framework:** Flask
* **Database:** SQLite with Flask-SQLAlchemy
* **Frontend:** HTML & vanilla JavaScript

## How to Run Locally

1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/wizzan1/Football_web.git](https://github.com/wizzan1/Football_web.git)
    ```
2.  **Navigate into the project directory:**
    ```bash
    cd Football_web
    ```
3.  **Install the required packages:**
    ```bash
    pip install -r requirements.txt
    ```
4.  **Create the database:**
    ```bash
    flask shell
    >>> from app import db, models
    >>> db.create_all()
    >>> exit()
    ```
5.  **Run the application:**
    ```bash
    python run.py
    ```
The application will be running at `http://127.0.0.1:5000/`.
