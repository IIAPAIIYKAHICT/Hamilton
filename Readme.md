# Hamilton Ventilator HL7 Client

This project provides a Python application to connect to Hamilton ventilators via a serial port (COM), parse real-time patient monitoring data, and generate HL7 observation messages.

The application can be compiled into a standalone executable for Raspberry Pi (Linux/ARM) or Windows, allowing it to run without needing a Python environment on the target machine.

---
##  Prerequisites

* **Git**: To clone the repository.
* **Python 3.9+**: For running the script directly or for native compilation.
* **Docker Desktop**: Required *only* for the cross-compilation method.

---
##  Project Setup

First, clone the repository and navigate into the project directory.

```bash
git clone <your-repository-url>
cd hamilton-project
```
It is recommended to create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows use venv\Scripts\activate
```
Install the required Python packages:

```bash
pip install -r requirements.txt
```
Choose one of the following methods to build the executable.

## Method 1: Build for Raspberry Pi via Docker 
This method allows you to create the Raspberry Pi executable on your main computer (Windows, macOS, or Linux) without needing to set up a development environment on the Pi itself.

1. Build the Docker Image:
This command uses buildx to create an image targeting the 32-bit ARM architecture (linux/arm/v7), which is compatible with most Raspberry Pi models.
```bash
docker buildx build --platform linux/arm/v7 --load -t hamilton-builder .

```
2. Run the Compiler:
This command runs the compiler inside the Docker container and mounts a local dist folder to retrieve the finished executable.
On Windows (PowerShell)
```bash
docker run --rm -v "${PWD}/dist:/app/dist" hamilton-builder
```
On macOS or Linux:
```bash
docker run --rm -v "$(pwd)/dist:/app/dist" hamilton-builder
```
A new folder named dist will be created in your project directory containing the executable hamilton_hl7_client.
## Method 2: Build Directly on Raspberry Pi
If you prefer to compile on the target device, follow these steps directly on your Raspberry Pi.

1. Setup the Project:
Clone the repository and install the dependencies on your Pi as described in the Project Setup section.

2. Install PyInstaller:

```bash
pip install pyinstaller
```
3. Run the Compiler:

```bash
pyinstaller --onefile --name hamilton_hl7_client test_connection.py
```
The executable hamilton_hl7_client will be created in the dist folder on your Raspberry Pi.



## Method 3: Build for Windows (.exe)
1. Setup the Project:
Clone the repository and install the dependencies on Windows as described in the Project Setup section.
2. Install PyInstaller:

```bash
pip install pyinstaller
```
3. Run the Compiler:
```bash
pyinstaller --onefile --name hamilton_hl7_client test_connection.py
```

## Running the Application
On Raspberry Pi (or Linux)
1. Copy the hamilton_hl7_client file to your Raspberry Pi.

2. Make the file executable:
```bash
chmod +x hamilton_hl7_client
```
Run the application:

```bash
./hamilton_hl7_client
``` 
On Windows
Navigate to the dist folder.

Double-click hamilton_hl7_client.exe or run it from the command line.