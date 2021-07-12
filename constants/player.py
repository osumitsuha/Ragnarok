from enum import IntEnum, IntFlag, unique


@unique
class Ranks(IntFlag):
    NONE = 0
    NORMAL = 1
    BAT = 2
    SUPPORTER = 4
    FRIEND = 8
    PEPPY = 16
    TOURNAMENT = 32


@unique
class PresenceFilter(IntEnum):
    NIL = 0
    ALL = 1
    FRIENDS = 2


@unique
class Privileges(IntEnum):
    BANNED = 1 << 0

    USER = 1 << 1
    VERIFIED = 1 << 2

    SUPPORTER = 1 << 3

    BAT = 1 << 4
    MODERATOR = 1 << 5
    ADMIN = 1 << 6
    DEV = 1 << 7

    PENDING = 1 << 8


@unique
class bStatus(IntEnum):
    IDLE = 0
    AFK = 1
    PLAYING = 2
    EDITING = 3
    MODDING = 4
    MULTIPLAYER = 5
    WATCHING = 6
    UNKNOWN = 7
    TESTING = 8
    SUBMITTING = 9
    PAUSED = 10
    LOBBY = 11
    MULTIPLAYING = 12
    OSUDIRECT = 13


country_codes = {
    "XX": 0,  # No/Unknown Country - Doesn't know where is it
    "AP": 1,  # Oceania
    "EU": 2,  # Europe
    "AD": 3,  # Andorra
    "AE": 4,  # UAE - United Arab Emirates
    "AF": 5,  # Afghanistan
    "AG": 6,  # Antigua
    "AI": 7,  # Anguilla
    "AL": 8,  # Albania
    "AM": 9,  # Armenia
    "AN": 10,  # Netherlands Antilles
    "AO": 11,  # Angola
    "AQ": 12,  # Antarctica
    "AR": 13,  # Argentina
    "AS": 14,  # American Samoa
    "AT": 15,  # Austria
    "AU": 16,  # Australia
    "AW": 17,  # Aruba
    "AZ": 18,  # Azerbaijan
    "BA": 19,  # Bosnia
    "BB": 20,  # Barbados
    "BD": 21,  # Bangladesh
    "BE": 22,  # Belgium
    "BF": 23,  # Burkina Faso
    "BG": 24,  # Bulgaria
    "BH": 25,  # Bahrain
    "BI": 26,  # Burundi
    "BJ": 27,  # Benin
    "BM": 28,  # Bermuda
    "BN": 29,  # Brunei Darussalam
    "BO": 30,  # Bolivia
    "BR": 31,  # Brazil
    "BS": 32,  # Bahamas
    "BT": 33,  # Bhutan
    "BV": 34,  # Bouvet Island
    "BW": 35,  # Botswana
    "BY": 36,  # Belarus
    "BZ": 37,  # Belize
    "CA": 38,  # Canada
    "CC": 39,  # Cocos Islands
    "CD": 40,  # Congo
    "CF": 41,  # Central African Republic
    "CG": 42,  # Congo, Democratic Republic of
    "CH": 43,  # Switzerland
    "CI": 44,  # Cote D'Ivoire
    "CK": 45,  # Cook Islands
    "CL": 46,  # Chile
    "CM": 47,  # Cameroon
    "CN": 48,  # China
    "CO": 49,  # Colombia
    "CR": 50,  # Costa Rica
    "CU": 51,  # Cuba
    "CV": 52,  # Cape Verd
    "CX": 53,  # Christmas Island
    "CY": 54,  # Cyprus
    "CZ": 55,  # Czech Republic
    "DE": 56,  # Germany
    "DJ": 57,  # Djibouti
    "DK": 58,  # Denmark
    "DM": 59,  # Dominica
    "DO": 60,  # Dominican Republic
    "DZ": 61,  # Algeria
    "EC": 62,  # Ecuador
    "EE": 63,  # Estonia
    "EG": 64,  # Egypt
    "EH": 65,  # Western Sahara
    "ER": 66,  # Eritrea
    "ES": 67,  # Spain
    "ET": 68,  # Ethiopia
    "FI": 69,  # Finland
    "FJ": 70,  # Fiji
    "FK": 71,  # Falkland Islands
    "FM": 72,  # Micronesia, Federated States of
    "FO": 73,  # Faroe Islands
    "FR": 74,  # France
    "FX": 75,  # France, Metropolitan
    "GA": 76,  # Gabon
    "GB": 77,  # United Kingdom
    "GD": 78,  # Grenada
    "GE": 79,  # Georgia
    "GF": 80,  # French Guiana
    "GH": 81,  # Ghana
    "GI": 82,  # Gibraltar
    "GL": 83,  # Greenland
    "GM": 84,  # Gambia
    "GN": 85,  # Guinea
    "GP": 86,  # Guadeloupe
    "GQ": 87,  # Equatorial Guinea
    "GR": 88,  # Greece
    "GS": 89,  # South Georgia
    "GT": 90,  # Guatemala
    "GU": 91,  # Guam
    "GW": 92,  # Guinea-Bissau
    "GY": 93,  # Guyana
    "HK": 94,  # Hong Kong
    "HM": 95,  # Heard Island
    "HN": 96,  # Honduras
    "HR": 97,  # Croatia
    "HT": 98,  # Haiti
    "HU": 99,  # Hungary
    "ID": 100,  # Indonesia
    "IE": 101,  # Ireland
    "IL": 102,  # Israel
    "IN": 103,  # India
    "IO": 104,  # British Indian Ocean Territory
    "IQ": 105,  # Iraq
    "IR": 106,  # Iran, Islamic Republic of
    "IS": 107,  # Iceland
    "IT": 108,  # Italy
    "JM": 109,  # Jamaica
    "JO": 110,  # Jordan
    "JP": 111,  # Japan
    "KE": 112,  # Kenya
    "KG": 113,  # Kyrgyzstan
    "KH": 114,  # Cambodia
    "KI": 115,  # Kiribati
    "KM": 116,  # Comoros
    "KN": 117,  # St. Kitts and Nevis
    "KP": 118,  # Korea, Democratic People's Republic of
    "KR": 119,  # Korea
    "KW": 120,  # Kuwait
    "KY": 121,  # Cayman Islands
    "KZ": 122,  # Kazakhstan
    "LA": 123,  # Lao
    "LB": 124,  # Lebanon
    "LC": 125,  # St. Lucia
    "LI": 126,  # Liechtenstein
    "LK": 127,  # Sri Lanka
    "LR": 128,  # Liberia
    "LS": 129,  # Lesotho
    "LT": 130,  # Lithuania
    "LU": 131,  # Luxembourg
    "LV": 132,  # Latvia
    "LY": 133,  # Libyan Arab Jamahiriya
    "MA": 134,  # Morocco
    "MC": 135,  # Monaco
    "MD": 136,  # Moldova, Republic of
    "MG": 137,  # Madagascar
    "MH": 138,  # Marshall Islands
    "MK": 139,  # Macedonia, the Former Yugoslav Republic of
    "ML": 140,  # Mali
    "MM": 141,  # Myanmar
    "MN": 142,  # Mongolia
    "MO": 143,  # Macau
    "MP": 144,  # Northern Mariana Islands
    "MQ": 145,  # Martinique
    "MR": 146,  # Mauritania
    "MS": 147,  # Montserrat
    "MT": 148,  # Malta
    "MU": 149,  # Mauritius
    "MV": 150,  # Maldives
    "MW": 151,  # Malawi
    "MX": 152,  # Mexico
    "MY": 153,  # Malaysia
    "MZ": 154,  # Mozambique
    "NA": 155,  # Namibia
    "NC": 156,  # New Caledonia
    "NE": 157,  # Niger
    "NF": 158,  # Norfolk Island
    "NG": 159,  # Nigeria
    "NI": 160,  # Nicaragua
    "NL": 161,  # Netherlands
    "NO": 162,  # Norway
    "NP": 163,  # Nepal
    "NR": 164,  # Nauru
    "NU": 165,  # Niue
    "NZ": 166,  # New Zealand
    "OM": 167,  # Oman
    "PA": 168,  # Panama
    "PE": 169,  # Peru
    "PF": 170,  # French Polynesia
    "PG": 171,  # Papua New Guinea
    "PH": 172,  # Philippines
    "PK": 173,  # Pakistan
    "PL": 174,  # Poland
    "PM": 175,  # St. Pierre
    "PN": 176,  # Pitcairn
    "PR": 177,  # Puerto Rico
    "PS": 178,  # Palestinian Territory
    "PT": 179,  # Portugal
    "PW": 180,  # Palau
    "PY": 181,  # Paraguay
    "QA": 182,  # Qatar
    "RE": 183,  # Reunion
    "RO": 184,  # Romania
    "RU": 185,  # Russian Federation
    "RW": 186,  # Rwanda
    "SA": 187,  # Saudi Arabia
    "SB": 188,  # Solomon Islands
    "SC": 189,  # Seychelles
    "SD": 190,  # Sudan
    "SE": 191,  # Sweden
    "SG": 192,  # Singapore
    "SH": 193,  # St. Helena
    "SI": 194,  # Slovenia
    "SJ": 195,  # Svalbard and Jan Mayen
    "SK": 196,  # Slovakia
    "SL": 197,  # Sierra Leone
    "SM": 198,  # San Marino
    "SN": 199,  # Senegal
    "SO": 200,  # Somalia
    "SR": 201,  # Suriname
    "ST": 202,  # Sao Tome and Principe
    "SV": 203,  # El Salvador
    "SY": 204,  # Syrian Arab Republic
    "SZ": 205,  # Swaziland
    "TC": 206,  # Turks and Caicos Islands
    "TD": 207,  # Chad
    "TF": 208,  # French Southern Territories
    "TG": 209,  # Togo
    "TH": 210,  # Thailand
    "TJ": 211,  # Tajikistan
    "TK": 212,  # Tokelau
    "TM": 213,  # Turkmenistan
    "TN": 214,  # Tunisia
    "TO": 215,  # Tonga
    "TL": 216,  # Timor-Leste
    "TR": 217,  # Turkey
    "TT": 218,  # Trinidad and Tobago
    "TV": 219,  # Tuvalu
    "TW": 220,  # Taiwan
    "TZ": 221,  # Tanzania
    "UA": 222,  # Ukraine
    "UG": 223,  # Uganda
    "UM": 224,  # US (Island)
    "US": 225,  # United States
    "UY": 226,  # Uruguay
    "UZ": 227,  # Uzbekistan
    "VA": 228,  # Holy See
    "VC": 229,  # St. Vincent
    "VE": 230,  # Venezuela
    "VG": 231,  # Virgin Islands, British
    "VI": 232,  # Virgin Islands, U.S.
    "VN": 233,  # Vietnam
    "VU": 234,  # Vanuatu
    "WF": 235,  # Wallis and Futuna
    "WS": 236,  # Samoa
    "YE": 237,  # Yemen
    "YT": 238,  # Mayotte
    "RS": 239,  # Serbia
    "ZA": 240,  # South Africa
    "ZM": 241,  # Zambia
    "ME": 242,  # Montenegro
    "ZW": 243,  # Zimbabwe
    "A1": 244,  # Unknown - Anonymous Proxy
    "A2": 245,  # Satellite Provider
    "O1": 246,  # Other
    "AX": 247,  # Aland Islands
    "GG": 248,  # Guernsey
    "IM": 249,  # Isle of Man
    "JE": 250,  # Jersey
    "BL": 251,  # St. Barthelemy
    "MF": 252,  # Saint Martin
}
