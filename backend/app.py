from flask import Flask
from flask_cors import CORS

from routes.games import games

app = Flask(__name__)
CORS(app)

app.register_blueprint(games, url_prefix="/games")

@app.route("/")
def home():
    return {"message": "RehabVerse Backend Running"}

if __name__ == "__main__":
    app.run(debug=True)