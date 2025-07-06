FROM python:3.10

RUN pip3 install --force-reinstall -v "requests==2.32.2"
RUN pip3 install --force-reinstall -v "cherrypy==18.8.0"
RUN pip3 install --force-reinstall -v "pycryptodome==3.21.0"
RUN pip3 install --force-reinstall -v "pydantic==2.10.6"
RUN pip3 install --force-reinstall -v "devtools==0.12.2"
