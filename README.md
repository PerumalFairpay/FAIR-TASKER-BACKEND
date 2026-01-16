# FAIRPAY HRM Backend

This is the backend for the FAIRPAY HRM project, built with FastAPI and MongoDB.

## Features

- **User Registration**: `POST /auth/register` with fields: `first_name`, `last_name`, `phone`, `email`, `department`, `hrm_id`, `password`.
- **User Login**: `POST /auth/login` with `email` and `password`.

## Prerequisites

1. **Python 3.8+**
2. **MongoDB** instance running locally (default: `mongodb://localhost:27017`) or configured via `.env`.

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. (Optional) Create a `.env` file in the root directory to configure the database:
   ```env
   MONGO_URL=mongodb://localhost:27017
   DB_NAME=fairpay_hrm_db
   ```

## Running with Docker (Recommended)

You can run both the backend and the MongoDB database easily using Docker Compose.

1.  **Build and Start**:
    ```bash
    docker-compose up --build
    ```
2.  **Access the API**:
    The API will be available at [http://localhost:8000](http://localhost:8000).

3.  **Stop**:
    Press `Ctrl+C` or run:
    ```bash
    docker-compose down
    ```

## Running Locally (Manual)

Run the application using `uvicorn`:

```bash
python -m uvicorn app.main:app --reload
```

## API Documentation

Once running, verify the API at:

- Swagger UI: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- ReDoc: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)
