# Football Web Manager

A web-based football management simulation game built with Python and Flask. This project features a full user authentication system, a SQLite database for persistence, and allows users to create and manage multiple teams.

## Features ✨
* Secure user registration and login system with password hashing.
* Data is stored in a SQLite database using the Flask-SQLAlchemy ORM.
* Users can create and own multiple teams (up to a maximum of 3).
* Each new team is automatically generated with a unique starter squad of 20 players.
* A central dashboard to view, manage, and delete all of a user's teams.
* A detailed team page to view a squad list, sorted by position.
* A professional, responsive UI built with Bootstrap 5.

## Technologies Used 🛠️
* **Backend:** Python
* **Web Framework:** Flask
* **Database:** SQLite with Flask-SQLAlchemy
* **Frontend:** HTML, Bootstrap 5, Jinja2

## How to Run Locally 🚀

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
