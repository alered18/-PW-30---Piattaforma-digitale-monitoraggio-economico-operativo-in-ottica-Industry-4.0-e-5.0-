FROM python:3.14-slim
WORKDIR /app
COPY pyproject.toml *.py ./
COPY simulatore ./simulatore
RUN pip install --no-cache-dir .
CMD ["python", "main.py"]
