FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

RUN uv init --no-readme && \
    uv add jupyterlab pandas numpy scikit-learn matplotlib seaborn joblib \
           mysql-connector-python sqlalchemy boto3

RUN mkdir -p /app/models

EXPOSE 8888

CMD ["uv", "run", "jupyter", "lab", "--ip=0.0.0.0", "--port=8888", "--no-browser", \
     "--allow-root", "--notebook-dir=/app/notebooks", \
     "--NotebookApp.token=mlops12345"]
