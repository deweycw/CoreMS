"""Docker utilities for managing CoreMS dependencies."""

import subprocess
import os
from pathlib import Path
from typing import Tuple, Optional


def get_corems_dir() -> Path:
    """Get the CoreMS directory path."""
    # Navigate up from hrms_viewer to find CoreMS root
    current = Path(__file__).parent.parent.parent
    if (current / "docker-compose.yml").exists():
        return current
    # Fallback to environment variable or default
    return Path(os.environ.get("COREMS_DIR", "/Users/christiandewey/CoreMS"))


def is_docker_available() -> bool:
    """Check if Docker is available on the system."""
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=10
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def is_molformdb_running() -> bool:
    """Check if the molformdb container is running."""
    try:
        result = subprocess.run(
            ["docker", "ps", "--filter", "name=molformdb", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
            timeout=10
        )
        # Check for either "molformdb" or "corems-molformdb" in container names
        return "molformdb" in result.stdout.lower()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def is_postgres_port_open() -> bool:
    """Check if PostgreSQL port 5432 is accessible."""
    import socket
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex(('localhost', 5432))
        sock.close()
        return result == 0
    except:
        return False


def start_molformdb() -> Tuple[bool, str]:
    """Start the molformdb container using docker-compose.

    Returns:
        Tuple of (success, message)
    """
    corems_dir = get_corems_dir()
    compose_file = corems_dir / "docker-compose.yml"

    if not compose_file.exists():
        return False, f"docker-compose.yml not found in {corems_dir}"

    try:
        # Try docker compose (v2) first, then docker-compose (v1)
        for cmd in [["docker", "compose"], ["docker-compose"]]:
            try:
                result = subprocess.run(
                    cmd + ["up", "-d"],
                    cwd=str(corems_dir),
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                if result.returncode == 0:
                    return True, "molformdb container started successfully"
                # If this command failed, try the next one
            except FileNotFoundError:
                continue

        return False, f"Failed to start container: {result.stderr}"

    except subprocess.TimeoutExpired:
        return False, "Timeout starting Docker container"
    except Exception as e:
        return False, f"Error starting container: {str(e)}"


def stop_molformdb() -> Tuple[bool, str]:
    """Stop the molformdb container.

    Returns:
        Tuple of (success, message)
    """
    corems_dir = get_corems_dir()

    try:
        for cmd in [["docker", "compose"], ["docker-compose"]]:
            try:
                result = subprocess.run(
                    cmd + ["down"],
                    cwd=str(corems_dir),
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                if result.returncode == 0:
                    return True, "molformdb container stopped"
            except FileNotFoundError:
                continue

        return False, f"Failed to stop container: {result.stderr}"

    except subprocess.TimeoutExpired:
        return False, "Timeout stopping Docker container"
    except Exception as e:
        return False, f"Error stopping container: {str(e)}"


def ensure_molformdb_running(output_callback=None) -> Tuple[bool, str]:
    """Ensure the molformdb container is running, starting it if needed.

    Args:
        output_callback: Optional callback function for status messages

    Returns:
        Tuple of (success, message)
    """
    def emit(msg):
        if output_callback:
            output_callback(msg + "\n")

    emit("Checking molecular formula database...")

    # First check if Docker is available
    if not is_docker_available():
        msg = "Docker is not available. Please start Docker Desktop."
        emit(f"ERROR: {msg}")
        return False, msg

    # Check if already running
    if is_molformdb_running():
        emit("molformdb container is already running")
        return True, "molformdb is running"

    # Check if port is in use by something else
    if is_postgres_port_open():
        emit("Port 5432 is open (PostgreSQL may be running locally)")
        return True, "PostgreSQL is accessible on port 5432"

    # Need to start the container
    emit("Starting molformdb container...")
    success, msg = start_molformdb()

    if success:
        # Wait a moment for PostgreSQL to be ready
        emit("Waiting for PostgreSQL to be ready...")
        import time
        for i in range(10):
            time.sleep(1)
            if is_postgres_port_open():
                emit("PostgreSQL is ready!")
                return True, "molformdb started and ready"

        emit("WARNING: Container started but PostgreSQL may not be ready yet")
        return True, "Container started (PostgreSQL may need more time)"
    else:
        emit(f"ERROR: {msg}")
        return False, msg
