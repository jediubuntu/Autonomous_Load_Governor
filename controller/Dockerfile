FROM python:3.12-slim

WORKDIR /alg

COPY controller ./controller
COPY llm ./llm

ENV PYTHONPATH=/alg

CMD ["python", "controller/main.py"]
