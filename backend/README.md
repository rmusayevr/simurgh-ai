# Simurgh AI

## Getting Started

Follow these steps to set up and run the project locally.

### Prerequisites

*   Python 3.12+
*   Poetry (install with `pip install poetry` if you don't have it)

### Setup

1.  **Clone the repository:**
    ```bash
    git clone <your-repo-url>
    cd simurgh-ai/backend
    ```

2.  **Install dependencies using Poetry:**
    ```bash
    poetry install
    ```

3.  **Activate the virtual environment (optional, but recommended):**
    ```bash
    poetry shell
    ```

4.  **Environment Variables:**
    Create a `.env` file in the `backend` directory based on `.env.example` (if one exists, otherwise, you'll need to know your required environment variables).

### Running the Application

To start the FastAPI application:

```bash
poetry run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

This command will start the server, and the API documentation will typically be available at `http://localhost:8000/docs`.

### Running Tests

To run the tests:

```bash
poetry run pytest
```