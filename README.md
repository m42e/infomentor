# Infomentor Tool

This tool is designed to check the infomentor portal and send notifications using mail or pushover api.

## Usage

```
python3 -m venv venv
source venv/bin/activate
python setup.py install
python -m infomentor
```

After the first run a `infomentor.ini` file is available which has a few values to be entered.

## Manage Users


### Step 1 create a user

Provide the username and password for infomentor.
```
source venv/bin/activate
python -m infomentor --adduser <username>
```
### Step 2 add notification mechanism
```
source venv/bin/activate
python -m infomentor --addmail <username>
```

or

```
source venv/bin/activate
python -m infomentor --addpushover <username>
```

### Step 3 (optional) Add iCloud calendar

It is capable of syncing all the infomentor calendar elements to icloud calendar

```
source venv/bin/activate
python -m infomentor --addcalendar <username>
```

## NB

The login process is a bit scary and mostly hacked. It happens often on the first run, that the login is not ready, the second run then should work without errors.

The script shall be run every 10 minutes, that will keep the session alive and minimize errors.

