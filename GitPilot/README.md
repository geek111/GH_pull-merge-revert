# GitPilot

GitPilot is a user-friendly desktop application for managing Git projects and GitHub repositories, built with Python and PyQt5.

## Prerequisites

*   Python 3.6+
*   pip (Python package installer)
*   Git (must be installed and in your system's PATH)

## Setup

1.  **Clone the repository (or download the source code):**
    ```bash
    # If it were a git repo:
    # git clone <repository_url>
    # cd GitPilot
    # For now, just ensure you are in the GitPilot directory containing main.py
    ```

2.  **Create a virtual environment (recommended):**
    ```bash
    python -m venv venv
    ```

3.  **Activate the virtual environment:**
    *   On Windows:
        ```bash
        .\venv\Scripts\activate
        ```
    *   On macOS/Linux:
        ```bash
        source venv/bin/activate
        ```

4.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

## Running the Application

Once the setup is complete, you can run GitPilot using:

```bash
python main.py
```
Or, if your `GitPilot` directory is not the current directory:
```bash
python path/to/GitPilot/main.py
```
