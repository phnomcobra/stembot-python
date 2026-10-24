FROM python:3.14-slim

RUN pip3 install --force-reinstall -v "requests==2.33.0"
RUN pip3 install --force-reinstall -v "pycryptodome==3.21.0"
RUN pip3 install --force-reinstall -v "pydantic==2.14.1"
RUN pip3 install --force-reinstall -v "devtools==0.12.2"
RUN pip3 install --force-reinstall -v "fastapi==0.135.3"
RUN pip3 install --force-reinstall -v "uvicorn==0.44.0"
