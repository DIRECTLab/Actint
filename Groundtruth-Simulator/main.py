from csv_print import csv_print_data, csv_print_header
from runfile import read_json
import sys

def main():
    try:
        vehicles, settings = read_json(sys.argv[1])  # Get filename from system arguments
    except IndexError:
        print("No runfile specified, using default 'example_ground_truth_runfile.json'")
        vehicles, settings = read_json("example_ground_truth_runfile.json")  # Get filename from default arguments

    filename: str = csv_print_header(settings.output_file)

    all_done=False
    while not all_done:
        """
        iterate through a list of vehicle objects and call their update methods
        """
        for v in vehicles:
            v.update(settings.time_step)
        csv_print_data(vehicles, filename, settings, settings.current_simulation_time)

        all_done = all(v.done == True for v in vehicles)
        settings.advance_time(settings.time_step)



if __name__== "__main__":
    main()