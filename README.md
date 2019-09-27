# Infomentor Tool

This tool is designed to check the infomentor portal and send notifications using mail or pushover api.

## Usage

```
python3 -m venv venv
source venv/bin/activate
python setup.py install
infomentor
```

After the first run a `infomentor.ini` file is available which has a few values to be entered.

## Manage Users


### Step 1 create a user

Provide the username and password for infomentor.
```
source venv/bin/activate
adduser --username <username>
```
### Step 2 add notification mechanism
```
source venv/bin/activate
addmail --username <username>
```

or

```
source venv/bin/activate
addpushover --username <username>
```

### Step 3 (optional) Add iCloud calendar

It is capable of syncing all the infomentor calendar elements to icloud calendar

```
source venv/bin/activate
addcalendar --username <username>
```

## NB

The login process is a bit scary and mostly hacked. It happens often on the first run, that the login is not ready, the second run then should work without errors.

The script shall be run every 10 minutes, that will keep the session alive and minimize errors.


## Docker

This could be run within docker. You it has a volume `/home/appuser` where all the data is stored. In favour of accessing it from a webserver you should bindmount it.
There also the infomentor.ini should be placed.

Build the container by `docker build -t infomentor:latest .` and run it like this:

```
docker run -v '/var/docker/infomentor/:/home/appuser' infomentor:latest
```

for adding an user or all the commands run it adding -it to it, like:

```
docker run -it -v '/var/docker/infomentor/:/home/appuser' infomentor:latest adduser
```

