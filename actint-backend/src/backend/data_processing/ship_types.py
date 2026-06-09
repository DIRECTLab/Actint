def classify_vessel(ship_type):

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