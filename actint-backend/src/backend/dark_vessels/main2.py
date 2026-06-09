from backend.dark_vessels.src.simulation.simulator import simulate_region
from backend.dark_vessels.src.classifiers.sequence_classifier import SequenceClassifier
from backend.mcp_servers.ais.helpers.vessel_query import get_vessel_position_history_helper

if __name__ == "__main__":
    data = simulate_region('philippines_eez')
    print(data)
    sq = SequenceClassifier()
    sq.fit(data, epochs=200)
    print(sq.predict(data))
    data = simulate_region('brazil_eez')
    sq.fit(data, epochs=200)
    print(sq.predict(data))
    data = simulate_region('strait_of_malacca')
    sq.fit(data, epochs=200)
    print(sq.predict(data))
    data = simulate_region('gulf_of_guinea')
    sq.fit(data, epochs=200)
    print(sq.predict(data))
    sq.save('sequence_classifier.pkl')

    vessel_locations = get_vessel_position_history_helper(209641000)
    vessel_locations_dataframe = sq.ais_to_dataframe(vessel_locations)
    print(sq.predict(vessel_locations_dataframe))

    