FROM python:3.12-slim

RUN pip3 install --force-reinstall -v "requests==2.32.2"
RUN pip3 install --force-reinstall -v "pycryptodome==3.21.0"
RUN pip3 install --force-reinstall -v "pydantic==2.10.6"
RUN pip3 install --force-reinstall -v "devtools==0.12.2"
RUN pip3 install --force-reinstall -v "fastapi==0.135.3"
RUN pip3 install --force-reinstall -v "uvicorn==0.44.0"
