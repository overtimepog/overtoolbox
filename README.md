# Dockerized Membean Automation

This project provides a Dockerized version of the Membean automation script, allowing it to run in an isolated container environment.

## Prerequisites

- Docker installed and running on your system
- Python 3.9 or later
- pip (Python package installer)

## Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd overtoolbox
```

2. Install Python dependencies:
```bash
pip install -r requirements.txt
```

## Usage

Run the automation script using the provided runner:

```bash
./run_membean.py -e <email> -p <password> -g <grade> -q <quiz>
```

### Parameters:

- `-e, --email`: Your Membean login email (required)
- `-p, --password`: Your Membean password (required)
- `-g, --grade`: Target grade level (required)
  - Valid options: A+, A, A-, B+, B, B-
- `-q, --quiz`: Enable quiz mode (optional)
  - Valid options: True, False
  - Default: False

### Example:

```bash
./run_membean.py -e user@example.com -p mypassword -g "A-" -q False
```

## How It Works

1. The script builds a Docker container with all necessary dependencies
2. Chrome browser runs in headless mode inside the container
3. The automation script executes in the isolated environment
4. Container is automatically cleaned up after completion

## Features

- Runs in an isolated Docker container for security
- Headless Chrome browser operation
- Automatic cleanup after completion
- Grade-based performance configuration
- Optional quiz mode support

## Troubleshooting

If you encounter issues:

1. Ensure Docker is running:
```bash
docker info
```

2. Check Docker build logs:
```bash
docker build -t membean-bot:latest .
```

3. Verify Python dependencies:
```bash
pip install -r requirements.txt
```

## Notes

- The container runs with a virtual display using Xvfb
- Chrome runs in headless mode for better performance
- All automation happens in an isolated environment
- Container and resources are automatically cleaned up after completion

## Security

- Credentials are only used within the isolated container
- Container is removed after completion
- No persistent storage of sensitive information
