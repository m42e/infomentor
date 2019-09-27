# Infomentor Tool

This tool is designed to check the infomentor portal and send notifications using mail or pushover api.
It is also capable of sending Calendar invitations/entries.

## Usage

You could install it locally but using the docker image is preferred.

```
python3 -m venv venv
source venv/bin/activate
python setup.py install
infomentor
```

After the first run a `infomentor.ini` file is available which has a few values to be entered.

## Docker

This could be run within docker. You it has a volume `/home/appuser` where all the data is stored. In favour of accessing it from a webserver you should bindmount it.
There also the infomentor.ini would be placed.

Build the container by `docker build -t infomentor:latest .` and run it like this:

### Notify Users / First Run

```
docker run -v '/var/docker/infomentor/:/home/appuser' infomentor:latest
```

### Adding a user

```
docker run -v '/var/docker/infomentor/:/home/appuser' infomentor:latest --username <uname> --password <pwd> --pushover <pushoverid> --invitationmail <mymail>
```

### See all options

```
docker run -v '/var/docker/infomentor/:/home/appuser' infomentor:latest --help
```

## Webserver Setup (nginx)

If you use the bindmount path as above:

```
location / {
 root /var/docker/infomentor/files;
}
```

## NB

The login process is a bit scary and mostly hacked. It happens often on the first run, that the login is not ready, the second run then should work without errors.

The script shall be run every 10 minutes, that will keep the session alive and minimize errors.

