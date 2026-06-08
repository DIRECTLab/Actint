AIS_VESSEL_TYPE_CODES = {
    0: "Not Available",

    # Wing In Ground (WIG)
    20: "WIG",
    21: "WIG Hazard A",
    22: "WIG Hazard B",
    23: "WIG Hazard C",
    24: "WIG Hazard D",
    29: "WIG Unspecified",

    # Special craft
    30: "Fishing",
    31: "Towing",
    32: "Towing Large Tow",
    33: "Dredging or Underwater Operations",
    34: "Diving Operations",
    35: "Military Operations",
    36: "Sailing Vessel",
    37: "Pleasure Craft",

    # High Speed Craft
    40: "High Speed Craft",
    41: "High Speed Craft Hazard A",
    42: "High Speed Craft Hazard B",
    43: "High Speed Craft Hazard C",
    44: "High Speed Craft Hazard D",
    49: "High Speed Craft Unspecified",

    # Service vessels
    50: "Pilot Vessel",
    51: "Search and Rescue",
    52: "Tug",
    53: "Port Tender",
    54: "Anti-Pollution Vessel",
    55: "Law Enforcement",
    56: "Spare Local Vessel",
    57: "Spare Local Vessel",
    58: "Medical Transport",
    59: "Noncombatant Vessel",

    # Passenger
    60: "Passenger",
    61: "Passenger Hazard A",
    62: "Passenger Hazard B",
    63: "Passenger Hazard C",
    64: "Passenger Hazard D",
    69: "Passenger Unspecified",

    # Cargo
    70: "Cargo",
    71: "Cargo Hazard A",
    72: "Cargo Hazard B",
    73: "Cargo Hazard C",
    74: "Cargo Hazard D",
    79: "Cargo Unspecified",

    # Tanker
    80: "Tanker",
    81: "Tanker Hazard A",
    82: "Tanker Hazard B",
    83: "Tanker Hazard C",
    84: "Tanker Hazard D",
    89: "Tanker Unspecified",

    # Other
    90: "Other",
    91: "Other Hazard A",
    92: "Other Hazard B",
    93: "Other Hazard C",
    94: "Other Hazard D",
    99: "Other Unspecified"
}


def get_ship_type(ship_type_code):
    return AIS_VESSEL_TYPE_CODES.get(ship_type_code, "Type Not Found")

def get_vessel_class(ship_type):

    # Not available
    if ship_type == 0:
        return "Unknown"

    # Wing In Ground craft
    elif 20 <= ship_type <= 29:
        return "Wing In Ground"

    # Fishing
    elif ship_type == 30:
        return "Fishing"

    # Towing
    elif ship_type in [31, 32]:
        return "Towing"

    # Dredging / Underwater Ops
    elif ship_type == 33:
        return "Dredging"

    # Diving Ops
    elif ship_type == 34:
        return "Diving Operations"

    # Military
    elif ship_type == 35:
        return "Military"

    # Sailing
    elif ship_type == 36:
        return "Sailing"

    # Pleasure Craft
    elif ship_type == 37:
        return "Pleasure Craft"

    # High Speed Craft
    elif 40 <= ship_type <= 49:
        return "High Speed Craft"

    # Service Vessels
    elif ship_type == 50:
        return "Pilot Vessel"

    elif ship_type == 51:
        return "Search And Rescue"

    elif ship_type == 52:
        return "Tug"

    elif ship_type == 53:
        return "Port Tender"

    elif ship_type == 54:
        return "Anti Pollution"

    elif ship_type == 55:
        return "Law Enforcement"

    elif ship_type in [56, 57]:
        return "Local Service Vessel"

    elif ship_type == 58:
        return "Medical Transport"

    elif ship_type == 59:
        return "Noncombatant"

    # Passenger
    elif 60 <= ship_type <= 69:
        return "Passenger"

    # Cargo
    elif 70 <= ship_type <= 79:
        return "Cargo"

    # Tanker
    elif 80 <= ship_type <= 89:
        return "Tanker"

    # Other
    elif 90 <= ship_type <= 99:
        return "Other"

    return "Unknown"

AIS_COUNTRY_CODES = {
    201: "Albania",
    202: "Andorra",
    203: "Austria",
    204: "Azores",
    205: "Belgium",
    206: "Belarus",
    207: "Bulgaria",
    208: "Vatican",
    209: "Cyprus",
    210: "Cyprus",
    211: "Germany",
    212: "Cyprus",
    213: "Georgia",
    214: "Moldova",
    215: "Malta",
    216: "Armenia",
    218: "Germany",
    219: "Denmark",
    220: "Denmark",
    224: "Spain",
    225: "Spain",
    226: "France",
    227: "France",
    228: "France",
    229: "Malta",
    230: "Finland",
    231: "Faroe Islands",
    232: "United Kingdom",
    233: "United Kingdom",
    234: "United Kingdom",
    235: "United Kingdom",
    236: "Gibraltar",
    237: "Greece",
    238: "Croatia",
    239: "Greece",
    240: "Greece",
    241: "Greece",
    242: "Morocco",
    243: "Hungary",
    244: "Netherlands",
    245: "Netherlands",
    246: "Netherlands",
    247: "Italy",
    248: "Malta",
    249: "Malta",
    250: "Ireland",
    251: "Iceland",
    252: "Liechtenstein",
    253: "Luxembourg",
    254: "Monaco",
    255: "Madeira",
    256: "Malta",
    257: "Norway",
    258: "Norway",
    259: "Norway",
    261: "Poland",
    262: "Montenegro",
    263: "Portugal",
    264: "Romania",
    265: "Sweden",
    266: "Sweden",
    267: "Slovakia",
    268: "San Marino",
    269: "Switzerland",
    270: "Czech Republic",
    271: "Turkey",
    272: "Ukraine",
    273: "Russia",
    274: "North Macedonia",
    275: "Latvia",
    276: "Estonia",
    277: "Lithuania",
    278: "Slovenia",
    279: "Serbia",
    301: "Anguilla",
    303: "Alaska (USA)",
    304: "Antigua and Barbuda",
    305: "Antigua and Barbuda",
    306: "Netherlands Antilles",
    307: "Aruba",
    308: "Bahamas",
    309: "Bahamas",
    310: "Bermuda",
    311: "Bahamas",
    312: "Belize",
    314: "Barbados",
    316: "Canada",
    319: "Cayman Islands",
    321: "Costa Rica",
    323: "Cuba",
    325: "Dominica",
    327: "Dominican Republic",
    329: "Guadeloupe",
    330: "Grenada",
    331: "Greenland",
    332: "Guatemala",
    334: "Honduras",
    336: "Haiti",
    338: "United States",
    339: "Jamaica",
    341: "Saint Kitts and Nevis",
    343: "Saint Lucia",
    345: "Mexico",
    347: "Martinique",
    348: "Montserrat",
    350: "Nicaragua",
    351: "Panama",
    352: "Panama",
    353: "Panama",
    354: "Panama",
    355: "Panama",
    356: "Panama",
    357: "Panama",
    358: "Puerto Rico",
    359: "El Salvador",
    361: "Saint Pierre and Miquelon",
    362: "Trinidad and Tobago",
    364: "Turks and Caicos Islands",
    366: "United States",
    367: "United States",
    368: "United States",
    369: "United States",
    370: "Panama",
    371: "Panama",
    372: "Panama",
    373: "Panama",
    374: "Panama",
    375: "Saint Vincent and the Grenadines",
    376: "Saint Vincent and the Grenadines",
    377: "Saint Vincent and the Grenadines",
    378: "British Virgin Islands",
    379: "US Virgin Islands",
    401: "Afghanistan",
    403: "Saudi Arabia",
    405: "Bangladesh",
    408: "Bahrain",
    410: "Bhutan",
    412: "China",
    413: "China",
    414: "China",
    416: "Taiwan",
    417: "Sri Lanka",
    419: "India",
    422: "Iran",
    423: "Azerbaijan",
    425: "Iraq",
    428: "Israel",
    431: "Japan",
    432: "Japan",
    434: "Turkmenistan",
    436: "Kazakhstan",
    437: "Uzbekistan",
    438: "Jordan",
    440: "South Korea",
    441: "South Korea",
    443: "Palestine",
    445: "North Korea",
    447: "Kuwait",
    450: "Lebanon",
    451: "Kyrgyzstan",
    453: "Macao",
    455: "Maldives",
    457: "Mongolia",
    459: "Nepal",
    461: "Oman",
    463: "Pakistan",
    466: "Qatar",
    468: "Syria",
    470: "UAE",
    471: "UAE",
    472: "Tajikistan",
    473: "Yemen",
    477: "Hong Kong",
    478: "Bosnia and Herzegovina",
    501: "Antarctica",
    503: "Australia",
    506: "Myanmar",
    508: "Brunei",
    510: "Micronesia",
    511: "Palau",
    512: "New Zealand",
    514: "Cambodia",
    515: "Cambodia",
    516: "Christmas Island",
    518: "Cook Islands",
    520: "Fiji",
    523: "Cocos Islands",
    525: "Indonesia",
    529: "Kiribati",
    531: "Laos",
    533: "Malaysia",
    536: "Northern Mariana Islands",
    538: "Marshall Islands",
    540: "New Caledonia",
    542: "Niue",
    544: "Nauru",
    546: "French Polynesia",
    548: "Philippines",
    550: "Papua New Guinea",
    553: "Solomon Islands",
    555: "American Samoa",
    557: "Samoa",
    559: "Singapore",
    561: "Thailand",
    563: "Singapore",
    564: "Singapore",
    565: "Singapore",
    566: "Singapore",
    567: "Thailand",
    570: "Tonga",
    572: "Tuvalu",
    574: "Vietnam",
    576: "Vanuatu",
    577: "Vanuatu",
    578: "Wallis and Futuna",
    601: "South Africa",
    603: "Angola",
    605: "Algeria",
    607: "Saint Paul Island",
    608: "Ascension Island",
    609: "Burundi",
    610: "Benin",
    611: "Botswana",
    612: "Central African Republic",
    613: "Cameroon",
    615: "Congo",
    616: "Comoros",
    617: "Cape Verde",
    618: "Antarctica",
    619: "Ivory Coast",
    620: "Comoros",
    621: "Djibouti",
    622: "Egypt",
    624: "Ethiopia",
    625: "Eritrea",
    626: "Gabon",
    627: "Ghana",
    629: "Gambia",
    630: "Guinea-Bissau",
    631: "Equatorial Guinea",
    632: "Guinea",
    633: "Burkina Faso",
    634: "Kenya",
    635: "Antarctica",
    636: "Liberia",
    637: "Liberia",
    638: "South Sudan",
    642: "Libya",
    644: "Lesotho",
    645: "Mauritius",
    647: "Madagascar",
    649: "Mali",
    650: "Mozambique",
    654: "Mauritania",
    655: "Malawi",
    656: "Niger",
    657: "Nigeria",
    659: "Namibia",
    660: "Reunion",
    661: "Rwanda",
    662: "Sudan",
    663: "Senegal",
    664: "Seychelles",
    665: "Saint Helena",
    666: "Somalia",
    667: "Sierra Leone",
    668: "Sao Tome and Principe",
    669: "Swaziland",
    670: "Chad",
    671: "Togo",
    672: "Tunisia",
    674: "Tanzania",
    675: "Uganda",
    676: "DR Congo",
    677: "Tanzania",
    678: "Zambia",
    679: "Zimbabwe",
    701: "Argentina",
    710: "Brazil",
    720: "Bolivia",
    725: "Chile",
    730: "Colombia",
    735: "Ecuador",
    740: "Falkland Islands",
    745: "Guiana",
    750: "Guyana",
    755: "Paraguay",
    760: "Peru",
    765: "Suriname",
    770: "Uruguay",
    775: "Venezuela",
}

def get_country_from_ais_code(code: int | str) -> str:
    """
    Returns the country name for a given AIS MMSI prefix code.
    
    Args:
        code: First 3 digits of MMSI (int or string)

    Returns:
        Country name or "Unknown"
    """
    try:
        code = int(code)
    except (ValueError, TypeError):
        return "Unknown"

    return AIS_COUNTRY_CODES.get(code, "Unknown")