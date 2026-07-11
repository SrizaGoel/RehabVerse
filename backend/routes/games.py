from flask import Blueprint, jsonify, request
import os
import subprocess
import sys
import importlib
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[2]

if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))
    
games = Blueprint("games", __name__)

AVAILABLE_GAMES = [
    {
        "id": "forgotten_orchestra",
        "title": "Forgotten Orchestra",
        "exercise": "Side Arm Raise"
    },
    {
        "id": "fishing",
        "title": "Fishing Adventure",
        "exercise": "Elbow Raise"
    }
]

@games.route("/", methods=["GET"])
def get_games():
    return AVAILABLE_GAMES

GAME_MODULES = {
    "forgotten_orchestra": "forgotten_orchestra",
    "fishing": "fish",
    "front_arm_raise": "front_arm_raise",
    "leg_raise": "leg_raise",
    "paint_the_object": "paint_the_object",
    "belle_pose": "belle_pose"
}

@games.route("/start", methods=["POST"])
def start_game():

    data = request.get_json()
    game = data.get("game")

    if game not in GAME_MODULES:
        return jsonify({"error": "Game not found"}), 404

    try:
        module = importlib.import_module(f"games.{GAME_MODULES[game]}")

        result = module.main(data)

        return jsonify(result)

    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 500