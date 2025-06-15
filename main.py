from core.app import app  # Import the already configured app instance
import logging
import os

# Setup logging if needed
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
logger.debug("Starting application...")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # Using the PORT from environment variable
    app.run(host="0.0.0.0", port=port, debug=True)
