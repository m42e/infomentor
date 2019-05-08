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








TODO:

::

{'id': 1342049, 'title': 'Jade LZK HSU 1. und 2. Klasse', 'time': '10:30 - 11:30', 'notes': '', 'enumType': 'Custom1', 'type': 'cal-custom1', 'info': {'id': 0, 'type': None,
 'resources': [{'id': 589680, 'fileType': 'docx', 'title': 'Lernziele HSU das Jahr.docx', 'url': '/Resources/Resource/Download/589680?api=IM2', 'fileTypeName': 'Word processor', 'apiType': 'IM2', 'connectionId': 1342049, 'connectionType':
  'Calendar'}]}, 'establishmentName': None, 'date': '18.01.2019', 'isEditable': False, 'isDeletable': False, 'startDate': '2019-01-18', 'startTime': '10:30', 'endDate': '2019-01-18', 'endTime': '11:30', 'allDayEvent': False, 'resourcesNeed
	ingConnection': None, 'thirdPartyApiCalendarEventId': None, 'thirdPartyApiCalendarSeriesId': None, 'thirdPartyApiCalendarId': None, 'attendeeIds': None}
