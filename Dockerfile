FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y gcc build-essential zlib1g-dev

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt pyinstaller

COPY test_connection.py .

CMD ["pyinstaller", "--onefile", "--name", "hamilton_hl7_client", "test_connection.py"]