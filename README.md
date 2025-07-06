# stembot-python

## Testing and Linting
- `python3 -m unittest discover -v`
- `pylint stembot`

## Integration Testing
1. Start up containers to setup a network of bots
    - Install docker desktop
    - `docker compose up`
2. Install dependencies
    - `pip install -r requirements.txt`
