import folium

"""
This simply takes a list of AIS points and creates an html file that displays all of those points on a map."""

def build_ship_map_html(points, output_path="ship_map.html"):
    """Create an HTML map of ship points using only lat/lon coordinates."""
    valid = [(float(p["lat"]), float(p["lon"])) for p in points if p.get("lat") is not None and p.get("lon") is not None]
    if not valid:
        raise ValueError("No valid lat/lon points were provided.")

    lats = [lat for lat, _ in valid]
    lons = [lon for _, lon in valid]
    center = [sum(lats) / len(lats), sum(lons) / len(lons)]

    m = folium.Map(location=center, zoom_start=10, control_scale=True)
    folium.PolyLine(valid, color="blue", weight=3, opacity=0.8).add_to(m)
    for lat, lon in valid:
        folium.CircleMarker([lat, lon], radius=5, color="red", fill=True, fill_opacity=0.8).add_to(m)

    m.fit_bounds([[min(lats), min(lons)], [max(lats), max(lons)]])
    m.save(output_path)
    return output_path