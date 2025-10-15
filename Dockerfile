FROM python:3.12

WORKDIR /proyect

COPY ./ ./

RUN pip install --no-cache-dir -r requirements.txt
EXPOSE 5000

CMD ["python", "run.py"]