Yahoo Fantasy Database Generator Web App

This web application allows you to generate a SQLite database file containing all the data for your Yahoo Fantasy Hockey league. It uses the yfpy library to fetch data from the Yahoo Fantasy API.

How It Works

The app provides a simple web interface where you:

Paste the contents of your private.json credentials file.

Enter your Yahoo Fantasy League ID.

Click "Generate Database".

The backend, built with Flask, will then securely use your credentials to connect to the Yahoo API, fetch all league data, structure it in a SQLite database, and provide the .db file for you to download. The process can take a few minutes as it fetches a large amount of data.

How to Get Your Credentials (private.json)

This app requires you to authenticate with Yahoo. The yfpy library provides a command-line tool to make this easy.

Install yfpy locally:

pip install yfpy


Run the authentication command:
Create a directory to store your credentials (e.g., auth) and then run the command:

yfpy-auth auth


Follow the on-screen instructions:
This will open a browser window asking you to log in to Yahoo and grant access. Once you approve, it will generate a private.json file inside the auth directory.

Use the content:
Open the newly created auth/private.json file, copy its entire content, and paste it into the textarea on the web app.

How to Run Locally

Clone the repository.

Install dependencies:
Make sure you have Python 3 installed, then run:

pip install -r requirements.txt


Run the Flask app:

python app.py


Open your web browser and navigate to http://127.0.0.1:8080.

How to Deploy to Render

You can host this application for free on Render.

Push the code to a GitHub repository.

Create a new "Web Service" on Render and connect it to your GitHub repository.

Use the following settings during creation:

Runtime: Python 3

Build Command: pip install -r requirements.txt

Start Command: gunicorn app:app

Deploy the service. Once it's live, you can access it at the URL provided by Render and generate your database from anywhere.