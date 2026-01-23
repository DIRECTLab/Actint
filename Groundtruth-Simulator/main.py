from csv_print import csv_print_data, csv_print_header
from runfile import read_json
import sys

def main():
    default_filename: str = "JFN-Groudtruth-Simulator_result.csv"
    filename: str = csv_print_header(default_filename)
    try:
        vehicles:list = read_json(sys.argv[1])  # Get filename from system arguments
    except IndexError:
        vehicles:list = read_json("simulation_data.json")  # Get filename from default arguments


    all_done=False
    while not all_done:
        """
        iterate through a list of vehicle objects and call their update methods
        """
        for v in vehicles:
            v.update(1, 10000, 10000)
        csv_print_data(vehicles, filename)

        all_done = all(v.done == True for v in vehicles)




if __name__== "__main__":
    main()