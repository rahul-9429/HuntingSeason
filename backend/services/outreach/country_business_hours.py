import re
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

OTHER_COUNTRIES_KEY = "__other__"

_STANDARD_DAYS = (1, 2, 3, 4, 5, 7)
_GULF_DAYS = (1, 2, 3, 4, 7)

_LONG_HOURS = frozenset({"United States"})

_GULF_HOURS = frozenset(
    {
        "Algeria",
        "Bahrain",
        "Egypt",
        "Iraq",
        "Kuwait",
        "Libya",
        "Oman",
        "Qatar",
        "Saudi Arabia",
        "Syria",
        "United Arab Emirates",
        "Yemen",
    }
)

_LEVANT_HOURS = frozenset({"Israel", "Jordan"})

_TIMEZONES: tuple[tuple[str, str], ...] = (
    ("Afghanistan", "Asia/Kabul"),
    ("Albania", "Europe/Tirane"),
    ("Algeria", "Africa/Algiers"),
    ("American Samoa", "Pacific/Pago_Pago"),
    ("Andorra", "Europe/Andorra"),
    ("Angola", "Africa/Luanda"),
    ("Anguilla", "America/Anguilla"),
    ("Antarctica", "Antarctica/McMurdo"),
    ("Antigua & Barbuda", "America/Antigua"),
    ("Argentina", "America/Argentina/Buenos_Aires"),
    ("Armenia", "Asia/Yerevan"),
    ("Aruba", "America/Aruba"),
    ("Australia", "Australia/Sydney"),
    ("Austria", "Europe/Vienna"),
    ("Azerbaijan", "Asia/Baku"),
    ("Bahamas", "America/Nassau"),
    ("Bahrain", "Asia/Bahrain"),
    ("Bangladesh", "Asia/Dhaka"),
    ("Barbados", "America/Barbados"),
    ("Belarus", "Europe/Minsk"),
    ("Belgium", "Europe/Brussels"),
    ("Belize", "America/Belize"),
    ("Benin", "Africa/Porto-Novo"),
    ("Bermuda", "Atlantic/Bermuda"),
    ("Bhutan", "Asia/Thimphu"),
    ("Bolivia", "America/La_Paz"),
    ("Bosnia & Herzegovina", "Europe/Sarajevo"),
    ("Botswana", "Africa/Gaborone"),
    ("Brazil", "America/Sao_Paulo"),
    ("British Indian Ocean Territory", "Indian/Chagos"),
    ("British Virgin Islands", "America/Tortola"),
    ("Brunei", "Asia/Brunei"),
    ("Bulgaria", "Europe/Sofia"),
    ("Burkina Faso", "Africa/Ouagadougou"),
    ("Burundi", "Africa/Bujumbura"),
    ("Cabo Verde", "Atlantic/Cape_Verde"),
    ("Cambodia", "Asia/Phnom_Penh"),
    ("Cameroon", "Africa/Douala"),
    ("Canada", "America/Toronto"),
    ("Caribbean Netherlands", "America/Kralendijk"),
    ("Cayman Islands", "America/Cayman"),
    ("Central African Republic", "Africa/Bangui"),
    ("Chad", "Africa/Ndjamena"),
    ("Chile", "America/Santiago"),
    ("China", "Asia/Shanghai"),
    ("Christmas Island", "Indian/Christmas"),
    ("Cocos (Keeling) Islands", "Indian/Cocos"),
    ("Colombia", "America/Bogota"),
    ("Comoros", "Indian/Comoro"),
    ("Cook Islands", "Pacific/Rarotonga"),
    ("Costa Rica", "America/Costa_Rica"),
    ("Croatia", "Europe/Zagreb"),
    ("Cuba", "America/Havana"),
    ("Curaçao", "America/Curacao"),
    ("Cyprus", "Asia/Nicosia"),
    ("Czechia", "Europe/Prague"),
    ("Côte d'Ivoire", "Africa/Abidjan"),
    ("DR Congo", "Africa/Kinshasa"),
    ("Denmark", "Europe/Copenhagen"),
    ("Djibouti", "Africa/Djibouti"),
    ("Dominica", "America/Dominica"),
    ("Dominican Republic", "America/Santo_Domingo"),
    ("Ecuador", "America/Guayaquil"),
    ("Egypt", "Africa/Cairo"),
    ("El Salvador", "America/El_Salvador"),
    ("Equatorial Guinea", "Africa/Malabo"),
    ("Eritrea", "Africa/Asmara"),
    ("Estonia", "Europe/Tallinn"),
    ("Eswatini", "Africa/Mbabane"),
    ("Ethiopia", "Africa/Addis_Ababa"),
    ("Falkland Islands", "Atlantic/Stanley"),
    ("Faroe Islands", "Atlantic/Faroe"),
    ("Fiji", "Pacific/Fiji"),
    ("Finland", "Europe/Helsinki"),
    ("France", "Europe/Paris"),
    ("French Guiana", "America/Cayenne"),
    ("French Polynesia", "Pacific/Tahiti"),
    ("Gabon", "Africa/Libreville"),
    ("Gambia", "Africa/Banjul"),
    ("Georgia", "Asia/Tbilisi"),
    ("Germany", "Europe/Berlin"),
    ("Ghana", "Africa/Accra"),
    ("Gibraltar", "Europe/Gibraltar"),
    ("Greece", "Europe/Athens"),
    ("Greenland", "America/Nuuk"),
    ("Grenada", "America/Grenada"),
    ("Guadeloupe", "America/Guadeloupe"),
    ("Guam", "Pacific/Guam"),
    ("Guatemala", "America/Guatemala"),
    ("Guernsey", "Europe/Guernsey"),
    ("Guinea", "Africa/Conakry"),
    ("Guinea-Bissau", "Africa/Bissau"),
    ("Guyana", "America/Guyana"),
    ("Haiti", "America/Port-au-Prince"),
    ("Honduras", "America/Tegucigalpa"),
    ("Hong Kong", "Asia/Hong_Kong"),
    ("Hungary", "Europe/Budapest"),
    ("Iceland", "Atlantic/Reykjavik"),
    ("India", "Asia/Kolkata"),
    ("Indonesia", "Asia/Jakarta"),
    ("Iran", "Asia/Tehran"),
    ("Iraq", "Asia/Baghdad"),
    ("Ireland", "Europe/Dublin"),
    ("Isle of Man", "Europe/Isle_of_Man"),
    ("Israel", "Asia/Jerusalem"),
    ("Italy", "Europe/Rome"),
    ("Jamaica", "America/Jamaica"),
    ("Japan", "Asia/Tokyo"),
    ("Jersey", "Europe/Jersey"),
    ("Jordan", "Asia/Amman"),
    ("Kazakhstan", "Asia/Almaty"),
    ("Kenya", "Africa/Nairobi"),
    ("Kiribati", "Pacific/Tarawa"),
    ("Kosovo", "Europe/Belgrade"),
    ("Kuwait", "Asia/Kuwait"),
    ("Kyrgyzstan", "Asia/Bishkek"),
    ("Laos", "Asia/Vientiane"),
    ("Latvia", "Europe/Riga"),
    ("Lebanon", "Asia/Beirut"),
    ("Lesotho", "Africa/Maseru"),
    ("Liberia", "Africa/Monrovia"),
    ("Libya", "Africa/Tripoli"),
    ("Liechtenstein", "Europe/Vaduz"),
    ("Lithuania", "Europe/Vilnius"),
    ("Luxembourg", "Europe/Luxembourg"),
    ("Macao", "Asia/Macau"),
    ("Madagascar", "Indian/Antananarivo"),
    ("Malawi", "Africa/Blantyre"),
    ("Malaysia", "Asia/Kuala_Lumpur"),
    ("Maldives", "Indian/Maldives"),
    ("Mali", "Africa/Bamako"),
    ("Malta", "Europe/Malta"),
    ("Marshall Islands", "Pacific/Majuro"),
    ("Martinique", "America/Martinique"),
    ("Mauritania", "Africa/Nouakchott"),
    ("Mauritius", "Indian/Mauritius"),
    ("Mayotte", "Indian/Mayotte"),
    ("Mexico", "America/Mexico_City"),
    ("Micronesia", "Pacific/Chuuk"),
    ("Moldova", "Europe/Chisinau"),
    ("Monaco", "Europe/Monaco"),
    ("Mongolia", "Asia/Ulaanbaatar"),
    ("Montenegro", "Europe/Podgorica"),
    ("Montserrat", "America/Montserrat"),
    ("Morocco", "Africa/Casablanca"),
    ("Mozambique", "Africa/Maputo"),
    ("Myanmar", "Asia/Yangon"),
    ("Namibia", "Africa/Windhoek"),
    ("Nauru", "Pacific/Nauru"),
    ("Nepal", "Asia/Kathmandu"),
    ("Netherlands", "Europe/Amsterdam"),
    ("New Caledonia", "Pacific/Noumea"),
    ("New Zealand", "Pacific/Auckland"),
    ("Nicaragua", "America/Managua"),
    ("Niger", "Africa/Niamey"),
    ("Nigeria", "Africa/Lagos"),
    ("Niue", "Pacific/Niue"),
    ("Norfolk Island", "Pacific/Norfolk"),
    ("North Korea", "Asia/Pyongyang"),
    ("North Macedonia", "Europe/Skopje"),
    ("Northern Mariana Islands", "Pacific/Saipan"),
    ("Norway", "Europe/Oslo"),
    ("Oman", "Asia/Muscat"),
    ("Pakistan", "Asia/Karachi"),
    ("Palau", "Pacific/Palau"),
    ("Palestine", "Asia/Hebron"),
    ("Panama", "America/Panama"),
    ("Papua New Guinea", "Pacific/Port_Moresby"),
    ("Paraguay", "America/Asuncion"),
    ("Peru", "America/Lima"),
    ("Philippines", "Asia/Manila"),
    ("Pitcairn Islands", "Pacific/Pitcairn"),
    ("Poland", "Europe/Warsaw"),
    ("Portugal", "Europe/Lisbon"),
    ("Puerto Rico", "America/Puerto_Rico"),
    ("Qatar", "Asia/Qatar"),
    ("Republic of the Congo", "Africa/Brazzaville"),
    ("Romania", "Europe/Bucharest"),
    ("Russia", "Europe/Moscow"),
    ("Rwanda", "Africa/Kigali"),
    ("Réunion", "Indian/Reunion"),
    ("Samoa", "Pacific/Apia"),
    ("San Marino", "Europe/San_Marino"),
    ("Saudi Arabia", "Asia/Riyadh"),
    ("Senegal", "Africa/Dakar"),
    ("Serbia", "Europe/Belgrade"),
    ("Seychelles", "Indian/Mahe"),
    ("Sierra Leone", "Africa/Freetown"),
    ("Singapore", "Asia/Singapore"),
    ("Sint Maarten", "America/Lower_Princes"),
    ("Slovakia", "Europe/Bratislava"),
    ("Slovenia", "Europe/Ljubljana"),
    ("Solomon Islands", "Pacific/Guadalcanal"),
    ("Somalia", "Africa/Mogadishu"),
    ("South Africa", "Africa/Johannesburg"),
    ("South Georgia & South Sandwich Islands", "Atlantic/South_Georgia"),
    ("South Korea", "Asia/Seoul"),
    ("South Sudan", "Africa/Juba"),
    ("Spain", "Europe/Madrid"),
    ("Sri Lanka", "Asia/Colombo"),
    ("St Barthélemy", "America/St_Barthelemy"),
    ("St Helena", "Atlantic/St_Helena"),
    ("St Kitts & Nevis", "America/St_Kitts"),
    ("St Lucia", "America/St_Lucia"),
    ("St Martin", "America/Marigot"),
    ("St Pierre & Miquelon", "America/Miquelon"),
    ("St Vincent & Grenadines", "America/St_Vincent"),
    ("Sudan", "Africa/Khartoum"),
    ("Suriname", "America/Paramaribo"),
    ("Svalbard & Jan Mayen", "Arctic/Longyearbyen"),
    ("Sweden", "Europe/Stockholm"),
    ("Switzerland", "Europe/Zurich"),
    ("Syria", "Asia/Damascus"),
    ("São Tomé & Príncipe", "Africa/Sao_Tome"),
    ("Taiwan", "Asia/Taipei"),
    ("Tajikistan", "Asia/Dushanbe"),
    ("Tanzania", "Africa/Dar_es_Salaam"),
    ("Thailand", "Asia/Bangkok"),
    ("Timor-Leste", "Asia/Dili"),
    ("Togo", "Africa/Lome"),
    ("Tokelau", "Pacific/Fakaofo"),
    ("Tonga", "Pacific/Tongatapu"),
    ("Trinidad & Tobago", "America/Port_of_Spain"),
    ("Tunisia", "Africa/Tunis"),
    ("Turkey", "Europe/Istanbul"),
    ("Turkmenistan", "Asia/Ashgabat"),
    ("Turks & Caicos Islands", "America/Grand_Turk"),
    ("Tuvalu", "Pacific/Funafuti"),
    ("US Virgin Islands", "America/St_Thomas"),
    ("Uganda", "Africa/Kampala"),
    ("Ukraine", "Europe/Kyiv"),
    ("United Arab Emirates", "Asia/Dubai"),
    ("United Kingdom", "Europe/London"),
    ("United States", "America/New_York"),
    ("Uruguay", "America/Montevideo"),
    ("Uzbekistan", "Asia/Tashkent"),
    ("Vanuatu", "Pacific/Efate"),
    ("Vatican City", "Europe/Vatican"),
    ("Venezuela", "America/Caracas"),
    ("Vietnam", "Asia/Ho_Chi_Minh"),
    ("Wallis & Futuna", "Pacific/Wallis"),
    ("Western Sahara", "Africa/El_Aaiun"),
    ("Yemen", "Asia/Aden"),
    ("Zambia", "Africa/Lusaka"),
    ("Zimbabwe", "Africa/Harare"),
    ("Åland Islands", "Europe/Mariehamn"),
)


def _hours(name: str, zone: str) -> dict[str, Any]:
    if name in _GULF_HOURS:
        return {"timezone": zone, "start_hour": 8, "end_hour": 16, "default_days": list(_GULF_DAYS)}
    if name in _LEVANT_HOURS:
        return {"timezone": zone, "start_hour": 8, "end_hour": 17, "default_days": list(_GULF_DAYS)}
    end_hour = 20 if name in _LONG_HOURS else 17
    return {
        "timezone": zone,
        "start_hour": 8,
        "end_hour": end_hour,
        "default_days": list(_STANDARD_DAYS),
    }


COUNTRY_BUSINESS_HOURS: dict[str, dict[str, Any]] = {
    name: _hours(name, zone) for name, zone in _TIMEZONES
}

_UNTABLED = sorted((_LONG_HOURS | _GULF_HOURS | _LEVANT_HOURS) - set(COUNTRY_BUSINESS_HOURS))
if _UNTABLED:
    raise RuntimeError(f"Business-hour rules name countries missing from the table: {_UNTABLED}")

DEFAULT_BUSINESS_HOURS: dict[str, Any] = {
    "timezone": None,
    "start_hour": 8,
    "end_hour": 20,
    "default_days": list(_STANDARD_DAYS),
}

_NORMALIZED_LOOKUP = {name.strip().lower(): name for name in COUNTRY_BUSINESS_HOURS}
_BY_LENGTH_DESC = sorted(COUNTRY_BUSINESS_HOURS, key=len, reverse=True)


def get_business_hours(country: str | None) -> tuple[str, dict[str, Any]]:
    if not country:
        return OTHER_COUNTRIES_KEY, DEFAULT_BUSINESS_HOURS
    canonical = _NORMALIZED_LOOKUP.get(country.strip().lower())
    if canonical is None:
        for name in _BY_LENGTH_DESC:
            if re.search(rf"\b{re.escape(name)}\b", country, re.IGNORECASE):
                canonical = name
                break
    if canonical is not None:
        return canonical, COUNTRY_BUSINESS_HOURS[canonical]
    return OTHER_COUNTRIES_KEY, DEFAULT_BUSINESS_HOURS


def is_country_send_allowed(
    country: str | None, overrides: dict[str, list[int]], now_utc: datetime
) -> bool:
    key, cfg = get_business_hours(country)
    days = overrides.get(key) or cfg["default_days"]
    local = now_utc.astimezone(ZoneInfo(cfg["timezone"])) if cfg["timezone"] else now_utc
    return local.isoweekday() in days and cfg["start_hour"] <= local.hour < cfg["end_hour"]
