# stembot-python

## Testing and Linting
1. Setup virtual environment
    - `python -m venv venv`
    - `source venv/bin/activate`
    - `pip install -e '.[build]'`

2. Run unit tests
    - `python3 -m unittest discover -v`

3. Run linter
    - `pylint stembot`

## Integration Testing
1. Start up containers to setup a network of bots
    - Install docker desktop
    - `python -m build`
    - `docker compose up`
