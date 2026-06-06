import os

from app import create_app


app = create_app("development")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("BACKEND_PORT", "5050")))
