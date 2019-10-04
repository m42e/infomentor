import pytz
import icalendar
import datetime

def generate_vtimezone(timezone, for_date=None):
    if not timezone or 'utc' in timezone.lower():  # UTC doesn't need a timezone definition
        return None
    if not for_date:
        for_date = now()
    try:
        z = pytz.timezone(timezone)
    except pytz.UnknownTimeZoneError:
        z = pytz.timezone('Europe/Berlin')
    if not hasattr(z, '_utc_transition_times'):
        return None
    transitions = zip(z._utc_transition_times, z._transition_info)
    try:
        dst1, std1, dst2, std2 = filter(lambda x: x[0].year in (for_date.year, for_date.year + 1),
                                        transitions)
        if dst1[1][1].seconds == 0:
            return _vtimezone_with_dst(std1, dst1, std2, dst2, timezone)
        else:
            return _vtimezone_with_dst(dst1, std1, dst2, std2, timezone)

    except:
        std = transitions[-1]
        if std[0].year > for_date.year:
            return None
        return _vtimezone_without_dst(std, timezone)


def _vtimezone_without_dst(std, timezone):
    vtimezone = icalendar.Timezone(tzid=timezone)
    standard = icalendar.TimezoneStandard()
    utc_offset, dst_offset, tz_name = std[1]
    standard.add('dtstart', std[0])
    standard.add('tzoffsetfrom', utc_offset)
    standard.add('tzoffsetto', utc_offset)
    standard.add('tzname', tz_name)
    vtimezone.add_component(standard)
    return vtimezone


def _vtimezone_with_dst(dst1, std1, dst2, std2, timezone):
    vtimezone = icalendar.Timezone(tzid=timezone)
    daylight = icalendar.TimezoneDaylight()
    utc_offset, dst_offset, tz_name = dst1[1]
    offsetfrom = std1[1][0]
    daylight.add('dtstart', dst1[0] + offsetfrom)
    daylight.add('rdate', dst1[0] + offsetfrom)
    daylight.add('rdate', dst2[0] + offsetfrom)
    daylight.add('tzoffsetfrom', offsetfrom)
    daylight.add('tzoffsetto', utc_offset)
    daylight.add('tzname', tz_name)
    vtimezone.add_component(daylight)

    standard = icalendar.TimezoneStandard()
    utc_offset, dst_offset, tz_name = std1[1]
    offsetfrom = dst1[1][0]
    standard.add('dtstart', std1[0] + offsetfrom)
    standard.add('rdate', std1[0] + offsetfrom)
    standard.add('rdate', std2[0] + offsetfrom)
    standard.add('tzoffsetfrom', offsetfrom)
    standard.add('tzoffsetto', utc_offset)
    standard.add('tzname', tz_name)
    vtimezone.add_component(standard)
    return vtimezone
