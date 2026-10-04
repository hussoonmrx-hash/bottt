FROM python:3.10-slim

WORKDIR /app

RUN pip install --no-cache-dir --upgrade pip

# Copy requirements and install them
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

EXPOSE 10000

# Run the bot
CMD ["python", "main.py"]
