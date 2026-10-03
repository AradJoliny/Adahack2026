from flask import Flask, redirect, render_template, url_for

app = Flask(__name__)


# 1. Start Page (Welcome screen)
@app.route("/")
def start():
  return render_template("start.html")


# 2. Main Page (Where the Start button takes you)
@app.route("/main")
def main():
  return render_template("main.html")


if __name__ == "__main__":
  # debug=True automatically reloads the server when you change files
  app.run(debug=True, port=5000)
