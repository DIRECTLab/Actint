AIS_SHIP_TYPES = {
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
    return AIS_SHIP_TYPES.get(ship_type_code, "Type Not Found")

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