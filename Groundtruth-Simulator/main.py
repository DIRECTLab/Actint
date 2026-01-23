from csv_print import csv_print_data, csv_print_header
from runfile import read_json
from classes import Settings
import sys

def main():
    default_filename: str = "JFN-Groudtruth-Simulator_result.csv"
    filename: str = csv_print_header(default_filename)
    try:
        vehicles, settings = read_json(sys.argv[1])  # Get filename from system arguments
    except IndexError:
        vehicles, settings = read_json("example_ground_truth_runfile.json")  # Get filename from default arguments


    all_done=False
    while not all_done:
        """
        iterate through a list of vehicle objects and call their update methods
        """
        for v in vehicles:
            v.update(settings.default_time_step)
        csv_print_data(vehicles, filename, settings)

        all_done = all(v.done == True for v in vehicles)




if __name__== "__main__":
    main()